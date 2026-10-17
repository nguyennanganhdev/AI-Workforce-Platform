"""Install additive OP2 reference/skill candidates; never evaluate or embed.

Run inside the deployed app with its environment. Requires explicit owner
and an active matching BQL account. Existing agents and KBs are untouched.
"""
import argparse
import asyncio
import hashlib
import os
from datetime import datetime, timezone
from uuid import UUID, uuid5, NAMESPACE_URL

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from agentscope.app.storage import (RedisStorage, KnowledgeBaseRecord, KnowledgeBaseData, EmbeddingModelConfig,
                                    KnowledgeDocumentRecord, KnowledgeDocumentData, SkillRecord)

REFERENCES = {
    '01-pham-vi-bql.md': ('Phạm vi BQL', 'BQL chỉ được đọc tài nguyên thuộc tài khoản hoặc tài nguyên đã chia sẻ. Quyền quản trị Domain cần binding đúng tài khoản và khu. Không dùng mã khu do người hỏi cung cấp để tự nâng quyền.'),
    '02-agent-nhap-va-phat-hanh.md': ('Bản nháp và bản phát hành', 'AgentSpec là cấu hình nghiệp vụ có version. Tạo thủ công lưu bản nháp. Phát hành cần báo cáo đánh giá hợp lệ của đúng spec. Readiness cấu hình không chứng minh chất lượng model. Không gửi chat agent nháp để vượt cổng phát hành.'),
    '03-chat-ca-nhan.md': ('Chat cá nhân', 'Hội thoại cá nhân giữ vai trò của agent và tài nguyên được phép. Không tự mời thành viên hoặc giao việc từ chat cá nhân. Chỉ dùng thông tin trong hội thoại hiện tại và nguồn được cấp quyền, không đọc hội thoại riêng của người khác.'),
    '04-quy-trinh-nhom.md': ('Điều phối nhóm', 'Yêu cầu nhiều chuyên môn: điều phối xác định mục tiêu và tiêu chí hoàn thành; handoff cho chuyên viên; chuyên viên hỏi đồng đội khi thiếu phụ thuộc; gửi result; điều phối review trước khi tổng hợp. Lời chào không cần đánh thức toàn bộ thành viên.'),
    '05-phan-bien.md': ('Phản biện và sửa báo cáo', 'Dùng TeamSay review challenge khi báo cáo thiếu căn cứ hoặc mâu thuẫn. Nêu đúng điểm cần sửa, giữ phạm vi yêu cầu. Chuyên viên gửi result sửa lại, điều phối accept hoặc stop. Không biến đề xuất phân tích thành chứng cứ đã thực hiện.'),
    '06-bang-chung.md': ('Bằng chứng', 'Phân biệt phân tích đề xuất với thông tin đã được xác minh bằng kết quả tool hoặc nguồn đáng tin. Nêu mã nguồn tài liệu, version và thời điểm dữ liệu. Khi thiếu bằng chứng phải nói rõ, không tự tạo mã ticket, giá hoặc kết quả.'),
    '07-bao-cao-ticket.md': ('Danh sách và tổng hợp ticket', 'Tool vh_management_ticket_list trả danh sách phân trang và tổng số theo khu đã được cấp quyền. Tool vh_management_ticket_summary tổng hợp theo trạng thái. Khoảng từ ngày đến ngày cuối không bao gồm, tối đa 93 ngày, theo múi giờ Việt Nam. Không suy tổng toàn khu từ một trang dữ liệu.'),
    '08-sla-workload.md': ('SLA và tải công việc', 'Tool vh_management_sla_report đọc deadline trên ticket và số ticket thiếu deadline; không tính lại toàn bộ lịch sử chu kỳ SLA. Tool vh_management_workload đếm ticket chưa kết thúc theo đội được giao trong kỳ tạo ticket, không thay thế lịch chấm công nhân viên.'),
    '09-quyen-mcp.md': ('Grant MCP', 'Token khởi tạo dùng discovery/cấp grant. Ticket grant gắn ticket, workflow, tool và thời hạn. Management grant gắn binding BQL và các tool đọc quản trị. Hai loại quyền không thay thế cho nhau. Không đặt credential trong prompt hoặc SKILL.md.'),
    '10-thao-tac-ghi.md': ('Chấp thuận và đối soát', 'Tra cứu trước khi đề xuất dispatch, đổi lịch hoặc hủy. Thao tác ghi cần quyền phù hợp, điều kiện nghiệp vụ và chấp thuận đúng hành động; dùng idempotency và version khi API hỗ trợ. Mất phản hồi cần đọc operation trước khi thử lại, không tuyên bố thành công khi kết quả chưa rõ.'),
    '11-knowledge.md': ('Tài liệu và nguồn', 'Kho văn bản tìm kiếm không dùng embedding chỉ trả tài liệu approved còn hiệu lực. Tài liệu candidate hoặc retired không dùng để kết luận. Tài liệu Domain unverified là tham khảo, không phải nội quy hay biểu phí đã được BQL phê duyệt. Không tự nâng nhãn verified hàng loạt.'),
    '12-skill-va-gioi-han.md': ('Skill và giới hạn năng lực', 'Skill là hướng dẫn dùng các tài nguyên đã có, không tự tạo ra API nghiệp vụ. Skill mới lưu candidate, quản lý xem nội dung rồi duyệt; agent sau chọn từ catalog được phép. Công cụ du lịch hiện là mock. Kiểm tra vh_management_capabilities; khi giao dịch chưa hỗ trợ thì lập phương án và bàn giao người phụ trách.'),
}

SKILLS = {
    'intake-v1': 'Tiếp nhận: làm rõ mục tiêu, phân loại yêu cầu, ghi thông tin còn thiếu. Không tạo ticket hoặc trạng thái giả. Dùng dữ liệu BQL cung cấp và tài liệu được phép; chuyển điều phối khi cần nhiều chuyên môn.',
    'source-citation-v1': 'Tra cứu: chọn Knowledge phù hợp, kiểm tra hiệu lực và trạng thái duyệt, trích nguồn và version. Không có tài liệu thì báo thiếu nguồn; không biến tài liệu tham khảo unverified thành nội quy chính thức.',
    'ticket-report-v1': 'Báo cáo: dùng management ticket list/summary theo khoảng ngày và khu đã được cấp quyền. Đọc đủ trang hoặc dùng tổng server. Nêu thời điểm dữ liệu, ticket chưa kết thúc và dữ liệu thiếu; không suy tổng từ một ticket.',
    'consent-dispatch-v1': 'Điều phối: đọc ticket, kiểm tra quyền và nguồn nhân sự. Đề xuất thao tác cụ thể, nhận chấp thuận phù hợp, thực hiện bằng tool được cấp rồi đối soát operation. Không lặp ghi khi trạng thái kết quả chưa rõ.',
    'evidence-review-v1': 'Kiểm tra bằng chứng: tách nhận định, đề xuất và kết quả đã xác minh. Mỗi tuyên bố thực hiện cần tool receipt hiện tại đúng ticket. Thiếu chứng cứ thì yêu cầu bổ sung, không chấp nhận báo cáo chỉ dựa vào lời của agent.',
    'team-challenge-v1': 'Phản biện: chỉ ra mâu thuẫn hoặc điều kiện thiếu, hỏi đồng đội và dùng review challenge với yêu cầu sửa rõ ràng. Chuyên viên gửi result đã sửa, coordinator accept/stop. Giới hạn vòng trao đổi, chuyển BQL khi thiếu dữ liệu ngoài hệ thống.',
    'handover-v1': 'Bàn giao: liệt kê việc đã có bằng chứng, việc mới là đề xuất, người chịu trách nhiệm theo vai trò và điều kiện hoàn thành. Không đánh dấu nghiệm thu/hoàn tất khi chưa có bằng chứng và chấp thuận của đúng người.',
    'privacy-v1': 'Bảo vệ dữ liệu: chỉ dùng tài nguyên được cấp trong khu và hội thoại hiện tại. Không đọc hội thoại riêng khác, không đưa mật khẩu hoặc dữ liệu cư dân vào skill dùng lại. Chỉ trả dữ liệu tối thiểu cần cho yêu cầu BQL.',
}


async def install(owner):
    engine = create_async_engine(os.environ['AGENTSCOPE_SQL_URL'])
    async with engine.connect() as db:
        user = (await db.execute(text('select username,role,status,area_id from auth_users where id=:id'), {'id': UUID(owner)})).mappings().one()
    await engine.dispose()
    if user['role'] != 'AREA_MANAGER' or user['status'] != 'active' or user['area_id'] != 'ocean-park-2':
        raise ValueError('Explicit active OP2 BQL owner required')
    store = RedisStorage(host=os.environ['REDIS_HOST'], port=int(os.getenv('REDIS_PORT','6379')),
                         db=int(os.getenv('REDIS_DB','0')), password=os.getenv('REDIS_PASSWORD') or None)
    await store.__aenter__()
    try:
        kb_id = uuid5(NAMESPACE_URL, owner + '/op2-platform-reference-v1').hex
        existing = await store.get_knowledge_base(owner,kb_id)
        if existing is None:
            await store.upsert_knowledge_base(owner, KnowledgeBaseRecord(id=kb_id,user_id=owner,data=KnowledgeBaseData(
                name='Hướng dẫn Platform OP2',description='Tài liệu kỹ thuật từ mã nguồn; không thay nội quy và biểu phí BQL.',
                retrieval_mode='lexical',collection_name='',embedding_model_config=EmbeddingModelConfig(
                    type='lexical',credential_id='',model='lexical-no-embedding',dimensions=1))))
        created_docs=created_skills=0
        for filename,(title,body) in REFERENCES.items():
            doc_id = uuid5(NAMESPACE_URL, kb_id+'/'+filename).hex
            if await store.get_knowledge_document(owner,kb_id,doc_id):
                continue
            content = '# '+title+'\n\n'+body+'\n\nNguồn: hợp đồng và hành vi mã nguồn Platform/Domain. Đây là hướng dẫn phần mềm, không phải quy định vận hành được BQL ban hành.'
            await store.upsert_knowledge_document(owner, KnowledgeDocumentRecord(id=doc_id,user_id=owner,knowledge_base_id=kb_id,status='ready',data=KnowledgeDocumentData(
                filename=filename,size=len(content.encode()),content_type='text/markdown',blob_uri='inline://reference',
                text_content=content,review_status='approved',reviewed_by='release:source-contract-review',
                source_ref='repository://op2-resource-pack-v1/'+filename,version=hashlib.sha256(content.encode()).hexdigest(),chunk_count=1)))
            created_docs+=1
        for name,body in SKILLS.items():
            name='op2-'+name
            if await store.get_skill_by_name(owner,name):
                continue
            markdown='---\nname: '+name+'\ndescription: "Hướng dẫn nghiệp vụ đề xuất cho BQL OP2; cần duyệt"\n---\n\n'+body
            await store.upsert_skill(owner,SkillRecord(user_id=owner,name=name,description=body[:200],markdown=markdown,
                version=hashlib.sha256(markdown.encode()).hexdigest()[:16],enabled=False,review_status='candidate',tags=['op2','workflow','candidate']))
            created_skills+=1
        print({'knowledge_base_id':kb_id,'created_documents':created_docs,'created_skill_candidates':created_skills,
               'model_calls':0,'existing_agents_modified':False})
    finally:
        await store.aclose()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner',required=True)
    args=parser.parse_args()
    asyncio.run(install(args.owner))
