"""Model-led Reception: the model holds the conversation and chooses tools; code keeps the rules.

Runs beside the fixed graph (src/graph) and is selected with RECEPTION_AGENT=loop. It keeps no
state of its own: every turn reads the conversation and its open request from the backend.
"""
