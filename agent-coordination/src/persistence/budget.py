"""Atomic restart-safe quota. Unknown usage consumes its reserved upper bound.

Configured price is an upper bound, pinned by version; estimated costs are never
labelled provider-billed actual cost. No price/usage means explicit unknown.
"""
from decimal import Decimal
from adapters.backend.errors import AdapterError


class Budget:
    def __init__(self, store, *, scope, token_limit, cost_limit=None, price_version=None, price_per_token=None, tenant_token_limit=None, tenant_cost_limit=None):
        if type(token_limit) is not int or token_limit <= 0: raise ValueError('token_limit required')
        self.store,self.scope,self.tokens = store,scope,token_limit
        self.cost = self._decimal(cost_limit)
        self.rate = self._decimal(price_per_token)
        self.price_version = price_version
        self.tenant_tokens = tenant_token_limit
        self.tenant_cost = self._decimal(tenant_cost_limit)
        if tenant_token_limit is not None and (type(tenant_token_limit) is not int or tenant_token_limit <= 0):
            raise ValueError('invalid tenant quota')
        if tenant_token_limit is not None or self.tenant_cost is not None:
            import re
            if not re.fullmatch(r'[a-f0-9]{64}/[a-f0-9]{64}',scope): raise ValueError('scoped tenant quota key required')
        if (self.cost is not None or self.rate is not None or self.tenant_cost is not None) and not price_version:
            raise ValueError('versioned price required')

    @staticmethod
    def _decimal(value):
        if value is None: return None
        value=Decimal(str(value))
        if not value.is_finite() or value<0: raise ValueError('finite nonnegative amount required')
        return value

    async def reserve(self, call_id, tokens):
        if not call_id or type(tokens) is not int or tokens<=0: raise ValueError('invalid reservation')
        await self.store.put_once("budget_pin",self.scope,{"token_limit":self.tokens,"cost_limit":str(self.cost) if self.cost is not None else None,"price_version":self.price_version,"price_per_token":str(self.rate) if self.rate is not None else None})
        if self.tenant_tokens is not None or self.tenant_cost is not None:
            await self.store.put_once('budget_tenant_pin',self.scope.split('/')[0],
                {'tokens':self.tenant_tokens,'cost':str(self.tenant_cost) if self.tenant_cost is not None else None,
                 'price_version':self.price_version,'price_per_token':str(self.rate) if self.rate is not None else None})
        estimate = self.rate*tokens if self.rate is not None else None
        with self.store.atomic() as db:
            self.store._guard(db)
            if db.execute('SELECT 1 FROM ledger WHERE scope=? AND id=?',(self.scope,call_id)).fetchone():
                raise AdapterError('model_attempt_already_reserved')
            rows=db.execute('SELECT bound,used,cost FROM ledger WHERE scope=?',(self.scope,)).fetchall()
            if sum(used if used is not None else bound for bound,used,_ in rows)+tokens>self.tokens:
                raise AdapterError('budget_exhausted')
            if self.cost is not None:
                if estimate is None or any(cost is None for _,_,cost in rows): raise AdapterError('cost_unknown')
                if sum(Decimal(cost) for _,_,cost in rows)+estimate>self.cost: raise AdapterError('budget_exhausted')
            if self.tenant_tokens is not None or self.tenant_cost is not None:
                tenant_rows=db.execute('SELECT bound,used,cost FROM ledger WHERE scope LIKE ?', (self.scope.split('/')[0]+'/%',)).fetchall()
                if self.tenant_tokens is not None and sum(used if used is not None else bound for bound,used,_ in tenant_rows)+tokens > self.tenant_tokens:
                    raise AdapterError('tenant_budget_exhausted')
                if self.tenant_cost is not None:
                    if estimate is None or any(cost is None for _,_,cost in tenant_rows): raise AdapterError('cost_unknown')
                    if sum(Decimal(cost) for _,_,cost in tenant_rows)+estimate > self.tenant_cost: raise AdapterError('tenant_budget_exhausted')
            db.execute('INSERT INTO ledger VALUES (?,?,?,?,?,?)',(self.scope,call_id,tokens,None,str(estimate) if estimate is not None else None,'reserved'))

    async def retain_unknown(self, call_id):
        """Exception cleanup via accounting port; never overwrite known usage."""
        with self.store.atomic() as db:
            self.store._guard(db)
            row=db.execute('SELECT cost,status FROM ledger WHERE scope=? AND id=?',(self.scope,call_id)).fetchone()
            if not row: raise AdapterError('reservation_missing')
            if row[1] == 'reserved':
                status='usage_unknown_'+('estimated' if row[0] is not None else 'cost_unknown')
                db.execute('UPDATE ledger SET status=? WHERE scope=? AND id=?',(status,self.scope,call_id))

    async def reconcile(self, call_id, *, tokens=None, cost=None):
        if tokens is not None and (type(tokens) is not int or tokens<0): raise ValueError('invalid usage')
        actual=self._decimal(cost)
        if actual is not None and not self.price_version: raise ValueError('versioned cost required')
        with self.store.atomic() as db:
            self.store._guard(db)
            row=db.execute('SELECT bound,used,cost,status FROM ledger WHERE scope=? AND id=?',(self.scope,call_id)).fetchone()
            if not row: raise AdapterError('reservation_missing')
            if tokens is not None and tokens>row[0]: raise AdapterError('usage_exceeds_reservation')
            amount=actual if actual is not None else (self.rate*(tokens if tokens is not None else row[0]) if self.rate is not None else None)
            status=('known' if tokens is not None else 'usage_unknown')+('_actual' if actual is not None else '_estimated' if amount is not None else '_cost_unknown')
            encoded=str(amount) if amount is not None else None
            if row[3]!='reserved':
                if row[1:]!=(tokens,encoded,status): raise AdapterError('usage_conflict')
                return
            if self.cost is not None and actual is not None and row[2] is not None and actual>Decimal(row[2]):
                # Keep upper reservation and error; no release enabling extra calls.
                raise AdapterError('cost_exceeds_reservation')
            db.execute('UPDATE ledger SET used=?,cost=?,status=? WHERE scope=? AND id=?',(tokens,encoded,status,self.scope,call_id))


class ScopedBudgets:
    """Pin quotas per tenant/ticket/generation/run; factories never swap mid-run.

    This registry groups Supervisor repairs and remote continuations in the same
    run ledger. Production storage accounting remains an allocated Platform port.
    """
    def __init__(self, store, *, token_limit, cost_limit=None, price_version=None, price_per_token=None, tenant_token_limit=None, tenant_cost_limit=None):
        self.store=store
        self.options=dict(token_limit=token_limit,cost_limit=cost_limit,price_version=price_version,price_per_token=price_per_token,tenant_token_limit=tenant_token_limit,tenant_cost_limit=tenant_cost_limit)

    def for_scope(self, context):
        from adapters.backend.messages import fingerprint
        scope=fingerprint({'tenant':context.tenant_id,'ticket':context.ticket_id,'generation':context.ticket_generation,
            'workspace':context.workspace_id,'run':context.run_id})
        tenant=fingerprint({'tenant':context.tenant_id})
        return Budget(self.store,scope=tenant+'/'+scope,**self.options)
