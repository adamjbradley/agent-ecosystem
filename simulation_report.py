
from jinja2 import Template
from datetime import datetime
import json

# Sample data
entities = [
    {"id": "user_001", "type": "user", "roles": ["consumer"], "goals": ["eco-friendly"]},
    {"id": "org_001", "type": "organization", "roles": ["buyer"], "goals": ["bulk discounts"]},
    {"id": "regulator", "type": "policy", "roles": ["compliance"], "goals": ["reduce emissions"]}
]

links = [
    ("regulator", "org_001", "regulates"),
    ("org_001", "user_001", "delegates")
]

latex = Template(r'''
\documentclass{article}
\usepackage[a4paper,margin=1in]{geometry}
\usepackage{graphicx}
\title{Simulation Report: Policy-Aware Agent Ecosystem}
\date{\today}
\begin{document}
\maketitle
\section*{Entities}
\begin{itemize}
{% for e in entities %}
  \item \textbf{{ e.id }} ({{ e.type }}) Roles: {{ e.roles|join(', ') }}, Goals: {{ e.goals|join(', ') }}
{% endfor %}
\end{itemize}
\section*{Links}
\begin{itemize}
{% for src,tgt,label in links %}
  \item {{ src }} --{{ label }}--> {{ tgt }}
{% endfor %}
\end{itemize}
\end{document}
''')

with open("simulation_report.tex", "w") as f:
    f.write(latex.render(entities=entities, links=links))
print("Generated simulation_report.tex")
