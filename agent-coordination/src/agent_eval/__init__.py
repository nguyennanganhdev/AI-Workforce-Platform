"""Agent evaluation: six approved cases run end to end in the sandbox (four must pass), then three layers of scoring.

contracts  the case, trace and result shapes shared with the business API
checks     the nine code checks over the recorded trace (layer 1)
judge      the separate LLM judge with four criteria scored 1-5 (layer 2)
metrics    optional library metrics such as Ragas (layer 3)
generator  six cases from what the agent may do, never from its instructions
worker     claims runs from the API, drives the eval stack, reports results
"""
