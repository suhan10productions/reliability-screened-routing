# Manuscript for IJSS: Operations & Logistics

Build (from the package root, after the analyses):

    PYTHONPATH=code python code/certify.py            # screen-then-certify, fresh-day test
    PYTHONPATH=code python code/frontier.py           # cost of reliability, buffers vs padding
    PYTHONPATH=code python code/wrong_model.py        # plans judged under other delay models
    PYTHONPATH=code python code/amazon_search_check.py
    cd code && PYTHONPATH=. python3 nhsjs_tables.py && PYTHONPATH=. python3 ijss_tables.py && python3 build_ijss.py

Outputs: routing_model_ijss.pdf (named) and ijss_review.pdf (no identifying information).
Every number in the text comes from result_macros_*.tex or a generated table.
