-- Sign-in tries of the last five minutes (password_auth.rate_limit). Counted here and not in the API's memory,
-- so the limit is one for every copy of the API and a restart does not hand out a new budget.
-- Not tenant data: a person signs in before any tenant is chosen, like `sessions`. Rows older than the window
-- are removed by the next sign-in.

CREATE TABLE public.sign_in_attempts (
    -- sha256 of "ip:<caller address>" or "account:<sign-in name>": what is counted, never who it was.
    key text NOT NULL,
    at timestamp with time zone DEFAULT now() NOT NULL
);
CREATE INDEX sign_in_attempts_key_idx ON public.sign_in_attempts (key, at);
