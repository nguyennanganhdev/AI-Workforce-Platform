"""Knowledge search (migration 0013): a resident gets resident documents of the place they live in, and nothing else."""
import asyncio
import base64
import gzip
import json
import random
import unicodedata
from array import array
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from test_domain_database import CATEGORY, delegate, resident_message
from test_integration_auth import person
from test_resident_contract import TENANT, sql
from test_resident_contract import database as database  # noqa: F401 -- pytest fixture export

from vinhomes_api import knowledge
from vinhomes_api.mock_data import build

AN, BINH, DUNG = "mock-an", "mock-binh", "mock-dung"   # Sapphire S1.01; Sapphire S1.02; a tower home and a villa in Hải Âu


def uid(name):
    return str(uuid5(NAMESPACE_URL, "knowledge-test:" + name))


def vector(name):
    """The same 1536 numbers of length 1 for the same name."""
    rng = random.Random(name)
    values = [rng.gauss(0, 1) for _ in range(knowledge.DIMENSIONS)]
    norm = sum(v * v for v in values) ** 0.5
    return array("f", (v / norm for v in values)).tobytes()


def document(name, title, body, audience="resident", zone=None, buildings=(), embedded=True):
    return {"id": uid(name), "version_id": uid(name + ":v1"), "code": name + ".md", "title": title, "category": "resident-care", "audience": audience,
            "site": "ocean-park-1", "zone": zone, "buildings": list(buildings), "unverified": name == "villa", "metadata": {},
            "chunks": [{"id": uid(name + ":0"), "ordinal": 0, "heading_path": title, "text": body, "token_count": len(body.split()),
                        **({"embedding": base64.b64encode(vector(name)).decode()} if embedded else {})}]}


DOCUMENTS = [
    document("pool", "Giờ mở cửa bể bơi", "Bể bơi ngoài trời mở cửa từ 6 giờ đến 21 giờ mỗi ngày, nghỉ trưa thứ Hai để làm sạch."),
    document("villa", "Nội quy khu biệt thự Hải Âu", "Cổng khu biệt thự Hải Âu đóng lúc 23 giờ. Xe khách đăng ký trước tại chốt bảo vệ.", zone="hai-au"),
    document("escape", "Thoát hiểm tòa S1.01", "Tòa S1.01 có hai thang bộ thoát hiểm ở hai đầu hành lang. Điểm tập kết là sân trước sảnh.", zone="sapphire", buildings=["S1.01"]),
    document("cleaning", "Quy trình vệ sinh bể bơi", "Nhân viên vệ sinh bể bơi kiểm tra clo lúc 5 giờ, trước giờ mở cửa bể bơi.", audience="staff"),
    document("nowhere", "Nội quy một khu không có", "Bể bơi của khu này mở cửa cả đêm.", zone="khu-khong-co"),
]


def write(tmp_path, documents):
    path = tmp_path / "knowledge.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as out:
        for line in documents:
            out.write(json.dumps(line, ensure_ascii=False) + "\n")
    return path


@pytest.fixture(scope="module", autouse=True)
def world(database, tmp_path_factory):
    asyncio.run(build(database["admin"], "test", 42))
    done = asyncio.run(knowledge.load(database["admin"], write(tmp_path_factory.mktemp("knowledge"), DOCUMENTS), str(TENANT)))
    assert {k: done[k] for k in ("documents", "chunks", "embedded", "skipped")} == {"documents": 4, "chunks": 4, "embedded": 0, "skipped": 1}
    # A place the database does not have is reported and left out, never loaded for the whole site.
    assert done["problems"] == ["nowhere.md: no zone khu-khong-co"]
    assert sql(database, "select count(*) as n from vh_knowledge_documents where code='nowhere.md'")[0]["n"] == 0


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setenv("RECEPTION_DELEGATION_KEY", "cd" * 32)
    monkeypatch.delenv("VINHOMES_API_EMBEDDING_API_KEY", raising=False)

    async def refuse(texts, timeout):
        raise AssertionError("a test reached the embedding provider")
    monkeypatch.setattr(knowledge, "embed", refuse)


def ask(database, who, question, top=5):
    """Reception's call: the delegation of one resident message is the only credential."""
    with person(database, who) as c:
        channel, message = resident_message(c, "Hỏi đáp", question)
        token = delegate(c, channel, message, who)["token"]
        return c.post("/internal/knowledge/search", headers={"Authorization": "Bearer " + token}, json={"query": question, "topK": top})


def found(database, who, question):
    answer = ask(database, who, question)
    assert answer.status_code == 200, answer.text
    return answer.json()


def test_a_question_finds_its_document_typed_with_or_without_diacritics(database):
    for question in ("Bể bơi mở cửa mấy giờ?", "be boi mo cua may gio", unicodedata.normalize("NFD", "Bể bơi mở cửa mấy giờ?")):
        result = found(database, AN, question)
        assert UUID(result["retrievalRunId"]) and result["insufficientSources"] is False
        first = result["hits"][0]
        assert set(first) == {"rank", "chunkId", "documentId", "versionId", "title", "section", "text", "unverified", "score"}  # what both Reception clients read, and the score
        assert (first["rank"], first["documentId"], first["versionId"], first["chunkId"]) == (1, uid("pool"), uid("pool:v1"), uid("pool:0")), question
        assert first["title"] == first["section"] == "Giờ mở cửa bể bơi" and first["text"].startswith("Bể bơi ngoài trời") and first["unverified"] is False
    off_topic = found(database, AN, "Giá vàng hôm nay bao nhiêu?")
    assert off_topic["insufficientSources"] is True and off_topic["hits"] == []                                           # nothing close enough: say so


def test_a_resident_only_gets_documents_of_the_place_they_live_in(database):
    villa_only = sql(database, """select ur.user_id from unit_residents ur join units u on u.id=ur.unit_id where u.code like 'HA2.%' and ur.verification_status='verified'
        and ur.user_id not in (select user_id from unit_residents group by user_id having count(*)>1) order by ur.user_id limit 1""")[0]["user_id"]
    gate, escape = "Cổng khu biệt thự Hải Âu đóng lúc mấy giờ?", "Thang bộ thoát hiểm tòa S1.01 ở đâu?"
    theirs = found(database, villa_only, gate)["hits"][0]
    assert theirs["documentId"] == uid("villa") and theirs["unverified"] is True                                          # 1: the villa zone's own rules, marked unverified
    assert uid("villa") not in {hit["documentId"] for hit in found(database, AN, gate)["hits"]}                           # 2: not for a resident of the towers
    assert found(database, AN, escape)["hits"][0]["documentId"] == uid("escape")                                         # 3: S1.01's escape plan for S1.01
    assert uid("escape") not in {hit["documentId"] for hit in found(database, BINH, escape)["hits"]}                      # 4: not for S1.02, same zone
    assert found(database, villa_only, "Bể bơi mở cửa mấy giờ?")["hits"][0]["documentId"] == uid("pool")                 # 5: the site's documents for everyone


def test_staff_documents_never_reach_a_resident(database):
    question = "Quy trình vệ sinh bể bơi kiểm tra clo lúc mấy giờ?"
    assert uid("cleaning") not in {hit["documentId"] for hit in found(database, AN, question)["hits"]}

    async def as_staff():
        engine = create_async_engine(database["runtime"])
        try:
            async with engine.begin() as db:
                await db.execute(text("select set_config('app.tenant_id',:t,true)"), {"t": str(TENANT)})
                return await knowledge.search(db, TENANT, "staff", None, None, question, 5)
        finally:
            await engine.dispose()
    assert [hit["documentId"] for hit in asyncio.run(as_staff())["hits"]] == [uid("cleaning")]                            # the same function serves staff agents


def test_homes_in_two_zones_get_the_site_until_a_request_says_which_home(database):
    pool, gate = "Bể bơi mở cửa mấy giờ?", "Cổng khu biệt thự Hải Âu đóng lúc mấy giờ?"
    with person(database, DUNG) as c:
        channel, _ = resident_message(c, "Hỏi đáp", pool)

        def search(question):
            message = c.post(f"/resident/chats/{channel}/messages", json={"text": question, "client_message_id": str(uuid4())}).json()["id"]
            answer = c.post("/internal/knowledge/search", headers={"Authorization": "Bearer " + delegate(c, channel, message, DUNG)["token"]}, json={"query": question})
            assert answer.status_code == 200, answer.text
            return [hit["documentId"] for hit in answer.json()["hits"]]
        assert search(pool)[0] == uid("pool")                                                                             # 1: what holds for the whole site
        assert not {uid("villa"), uid("escape")} & set(search(gate) + search("Thang bộ thoát hiểm tòa S1.01 ở đâu?"))     # 2: and nothing of either home
        villa = next(u for u in c.get("/resident/me").json()["units"] if u["code"].startswith("HA2"))
        filed = c.post(f"/resident/chats/{channel}/tickets", headers={"Idempotency-Key": str(uuid4())}, json={
            "domain_id": villa["domain_id"], "building_id": villa["building_id"], "unit_id": villa["id"], "category_id": CATEGORY, "title": "Ổ điện hỏng",
            "description": "Ổ điện hỏng từ sáng.", "contact_name": "Cư dân", "contact_phone": "0900000000", "location": "Phòng khách", "request_kind": "incident"})
        assert filed.status_code in (200, 201), filed.text
        assert search(gate)[0] == uid("villa")                                                                            # 3: the request filed here names the home
    with person(database, AN) as c:                                                                                       # and without a delegation nobody searches
        assert c.post("/internal/knowledge/search", json={"query": "bể bơi"}).status_code == 401


def test_loading_the_same_file_again_writes_nothing(database, tmp_path):
    def state():
        return sql(database, "select 'd' as t,id,xmin::text as x,updated_at from vh_knowledge_documents union all select 'c',id,xmin::text,updated_at from vh_knowledge_chunks order by 1,2")
    before = state()
    again = asyncio.run(knowledge.load(database["admin"], write(tmp_path, DOCUMENTS), str(TENANT)))
    assert again["changed"] == 0 and state() == before
    # A passage that lost its lines is rewritten, one that left the document is removed, and the rest stay as they were.
    edited = json.loads(json.dumps(DOCUMENTS[:4]))
    edited[0]["chunks"][0]["text"] += " Trẻ em đi cùng người lớn."
    edited[2]["chunks"] = []
    try:
        assert asyncio.run(knowledge.load(database["admin"], write(tmp_path, edited), str(TENANT)))["changed"] == 1
        assert sql(database, "select count(*) as n from vh_knowledge_chunks where document_id=$1", UUID(uid("escape")))[0]["n"] == 0
    finally:
        asyncio.run(knowledge.load(database["admin"], write(tmp_path, DOCUMENTS), str(TENANT)))
    assert [(r["t"], r["id"]) for r in state()] == [(r["t"], r["id"]) for r in before]


def test_meaning_ranks_when_the_question_can_be_embedded_and_words_answer_when_it_cannot(database, monkeypatch):
    question = "Khi có cháy thì chạy lối nào?"                                                                            # shares no telling word with the escape plan
    assert uid("escape") not in {hit["documentId"] for hit in found(database, AN, question)["hits"]}                      # 1: no key: words only
    monkeypatch.setenv("VINHOMES_API_EMBEDDING_API_KEY", "test-key")
    calls = []

    async def same_as_escape(texts, timeout):
        calls.append(texts)
        return [vector("escape")]
    monkeypatch.setattr(knowledge, "embed", same_as_escape)
    first = found(database, AN, question)["hits"][0]
    assert first["documentId"] == uid("escape") and first["score"] >= 0.8 and calls == [[question]]                       # 2: the question is embedded as typed
    found(database, AN, unicodedata.normalize("NFD", question))
    assert calls[-1] == [question]                                                                                        #    letters typed as base and marks are joined first
    assert uid("villa") not in {hit["documentId"] for hit in found(database, AN, "Cổng khu biệt thự Hải Âu")["hits"]}     # 3: the place still comes first

    async def down(texts, timeout):
        raise OSError("provider down")
    monkeypatch.setattr(knowledge, "embed", down)
    assert found(database, AN, "Bể bơi mở cửa mấy giờ?")["hits"][0]["documentId"] == uid("pool")                         # 4: provider down: words still answer

    async def unrelated(texts, timeout):
        return [vector("nothing here is about this")]
    monkeypatch.setattr(knowledge, "embed", unrelated)
    assert found(database, AN, "bể bơi")["insufficientSources"] is True                                                   # 5: two words that occur somewhere do not outvote the meaning
    assert found(database, AN, "be boi mo cua may gio")["hits"][0]["documentId"] == uid("pool")                           # 6: a whole question typed without diacritics does


def test_a_passage_without_a_vector_is_embedded_when_a_key_is_set(database, tmp_path, monkeypatch):
    extra = document("parking", "Chỗ đỗ xe khách", "Xe khách đỗ tại bãi ngoài trời cạnh cổng chính.", embedded=False)
    path = write(tmp_path, [extra])
    try:
        assert asyncio.run(knowledge.load(database["admin"], path, str(TENANT)))["embedded"] == 0                         # no key: loaded without a vector
        assert found(database, AN, "Xe khách đỗ ở đâu?")["hits"][0]["documentId"] == uid("parking")                      # and still found by its words
        monkeypatch.setenv("VINHOMES_API_EMBEDDING_API_KEY", "test-key")
        sent = []

        async def fake(texts, timeout):
            sent.extend(texts)
            return [vector("parking")] * len(texts)
        monkeypatch.setattr(knowledge, "embed", fake)
        assert asyncio.run(knowledge.load(database["admin"], path, str(TENANT)))["embedded"] == 1
        assert sent == ["Chỗ đỗ xe khách\n\nXe khách đỗ tại bãi ngoài trời cạnh cổng chính."]                             # the heading goes in with the passage
        assert sql(database, "select embedding=$2::text::vector as same from vh_knowledge_chunks where id=$1", UUID(uid("parking:0")), knowledge.literal(vector("parking")))[0]["same"]
        assert asyncio.run(knowledge.load(database["admin"], path, str(TENANT))) == {"documents": 1, "chunks": 1, "embedded": 0, "skipped": 0, "changed": 0, "problems": []}
    finally:
        sql(database, "delete from vh_knowledge_documents where id=$1 returning id", UUID(uid("parking")))


def test_the_api_role_cannot_read_another_tenants_knowledge(database, monkeypatch):
    other = uuid4()
    sql(database, "insert into tenants(id,code,name,status) values($1,'other-knowledge','Khu khác','active') returning id", other)
    sql(database, "insert into vh_knowledge_documents(id,tenant_id,code,version_id,title,category,audience) values($1,$2,'x.md',$1,'Tài liệu khu khác','resident-care','resident') returning id", other, other)
    pool = knowledge.literal(vector("pool"))                                                                              # the other site's passage means the same as this site's
    sql(database, """insert into vh_knowledge_chunks(id,tenant_id,document_id,ordinal,text_content,text_hash,token_count,search_tsv,embedding)
        values($1,$2,$1,0,'Bể bơi khu khác mở cửa cả đêm.','x',7,to_tsvector('simple','be boi khu khac mo cua ca dem'),$3::text::vector) returning id""", other, other, pool)

    async def visible(tenant):
        db = await asyncpg.connect(database["runtime"].replace("postgresql+asyncpg:", "postgresql:"))
        try:
            async with db.transaction():
                if tenant:
                    await db.execute("select set_config('app.tenant_id',$1,true)", str(tenant))
                await db.execute("set local enable_seqscan=off")                                                          # the nearest come through the vector index
                nearest = await db.fetch("select tenant_id from vh_knowledge_chunks order by embedding <=> $1::text::vector limit 2", pool)
                return (await db.fetchval("select count(*) from vh_knowledge_chunks"), await db.fetchval("select count(*) from vh_knowledge_chunks where tenant_id=$1", other),
                        [row["tenant_id"] for row in nearest])
        finally:
            await db.close()
    assert asyncio.run(visible(None)) == (0, 0, [])                                                                       # 1: no tenant: nothing, by count or by nearest vector
    assert asyncio.run(visible(TENANT)) == (4, 0, [TENANT, TENANT])                                                       # 2: its own tenant: its own passages only
    assert asyncio.run(visible(other)) == (1, 1, [other])
    assert all(hit["title"] != "Tài liệu khu khác" for hit in found(database, AN, "Bể bơi mở cửa cả đêm")["hits"])        # 3: and search does not cross over
    monkeypatch.setenv("VINHOMES_API_EMBEDDING_API_KEY", "test-key")

    async def same_as_pool(texts, timeout):
        return [vector("pool")]
    monkeypatch.setattr(knowledge, "embed", same_as_pool)
    assert [hit["documentId"] for hit in found(database, AN, "Bể bơi mở cửa cả đêm")["hits"]][:1] == [uid("pool")]        #    by meaning neither: the API role runs the vector search and gets its own
    assert all(hit["title"] != "Tài liệu khu khác" for hit in found(database, AN, "Bể bơi mở cửa cả đêm")["hits"])
    monkeypatch.delenv("VINHOMES_API_EMBEDDING_API_KEY")
    with pytest.raises(asyncpg.InsufficientPrivilegeError):                                                               # 4: the API reads knowledge, it does not write it
        sql({"admin": database["runtime"].replace("postgresql+asyncpg:", "postgresql:")}, "delete from vh_knowledge_chunks returning id")


def test_a_file_loaded_for_another_tenant_cannot_write_this_tenants_rows(database, tmp_path):
    other = uuid4()
    sql(database, "insert into tenants(id,code,name,status) values($1,'other-site','Khu khác','active') returning id", other)
    sql(database, "insert into domains(id,tenant_id,code,name,status) values($1,$1,'vinhomes','V','active') returning id", other)
    sql(database, "insert into sites(id,tenant_id,domain_id,code,name,address,status) values($1,$1,$1,'ocean-park-1','S','x','active') returning id", other)

    def pool():
        return sql(database, """select d.tenant_id,d.audience,d.title,k.tenant_id as chunk_tenant,k.document_id,k.text_content,d.xmin::text as dx,k.xmin::text as kx
            from vh_knowledge_documents d join vh_knowledge_chunks k on k.document_id=d.id where k.id=$1""", UUID(uid("pool:0")))
    before = pool()
    same_document = {**json.loads(json.dumps(DOCUMENTS[0])), "audience": "staff", "title": "Của khu khác"}               # the shared file, loaded for a second site
    same_document["chunks"][0]["text"] = "Nội dung nội bộ của khu khác."
    same_passage = {**document("theirs", "Của khu khác", "Nội dung nội bộ của khu khác."), "audience": "staff"}           # a new document that reuses one passage id
    same_passage["chunks"][0]["id"] = uid("pool:0")
    for name, theirs in (("pool.md", same_document), ("theirs.md", same_passage)):
        with pytest.raises(SystemExit, match=name):
            asyncio.run(knowledge.load(database["admin"], write(tmp_path, [theirs]), str(other)))
        assert pool() == before and before[0]["tenant_id"] == before[0]["chunk_tenant"] == TENANT
        assert sql(database, "select count(*) as n from vh_knowledge_documents where tenant_id=$1", other)[0]["n"] == 0   # nothing of a refused file stays
