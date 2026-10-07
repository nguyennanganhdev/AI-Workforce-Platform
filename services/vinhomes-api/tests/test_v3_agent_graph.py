"""Graph live counters exclude stale runs without deleting historical activity."""
from uuid import UUID, uuid4
from test_resident_contract import sql
from test_resident_contract import database as database
from test_v3_agent_database import demo_client
from test_v3_coordination import app, verified_team


def test_graph_live_metrics_and_inspector_ignore_finished_or_obsolete_requests(database):
    room='management-room'
    with demo_client(database,'management') as manager:
        baseline=manager.get('/rooms/'+room+'/agent-graph').json()
    cases={}
    with app(database) as runtime:
        for condition in ('live','completed','failed','cancelled','closed_ticket','cancelled_ticket','closed_member','obsolete_generation'):
            team=verified_team(runtime,database,'Graph '+condition+' '+uuid4().hex[:6])
            row=sql(database,"""select at.ticket_id,at.supervisor_agent_id,tm.id as member_id,r.id as run_id
                from agent_teams at join team_members tm on tm.team_id=at.id and tm.member_kind='supervisor'
                join agent_runs r on r.team_member_id=tm.id where at.id=$1""",UUID(team))[0]
            assert sql(database,'select status from agent_runs where id=$1',row['run_id'])[0]['status']=='running'
            sql(database,"update agent_teams set status='running' where id=$1 returning id",UUID(team))
            cases[condition]={**row,'team':UUID(team)}
    for condition in ('completed','failed','cancelled'):
        sql(database,'update agent_teams set status=$2 where id=$1 returning id',cases[condition]['team'],condition)
    for condition,status in (('closed_ticket','closed'),('cancelled_ticket','cancelled')):
        sql(database,'update tickets set status=$2 where id=$1 returning id',cases[condition]['ticket_id'],status)
    sql(database,"update team_members set status='closed' where id=$1 returning id",cases['closed_member']['member_id'])
    sql(database,'update tickets set reopen_count=reopen_count+1 where id=$1 returning id',cases['obsolete_generation']['ticket_id'])
    supervisor=cases['live']['supervisor_agent_id']
    assert all(case['supervisor_agent_id']==supervisor for case in cases.values())
    with demo_client(database,'management') as manager:
        response=manager.get('/rooms/'+room+'/agent-graph')
        assert response.status_code==200,response.text
        graph=response.json()
    metrics=graph['metrics'][supervisor]
    assert metrics['running']==baseline['metrics'][supervisor]['running']+1
    assert graph['summary']['running_sessions']==baseline['summary']['running_sessions']+1
    own_sessions={str(session['id']) for session in graph['sessions']} & {str(case['team']) for case in cases.values()}
    assert own_sessions=={str(cases['live']['team'])}
    # All eight observed runs remain in historical counters, including ended work.
    assert metrics['seven_days']==baseline['metrics'][supervisor]['seven_days']+len(cases)
    assert metrics['today']==baseline['metrics'][supervisor]['today']+len(cases)
    assert all(sql(database,'select status from agent_runs where id=$1',case['run_id'])[0]['status']=='running' for case in cases.values())
