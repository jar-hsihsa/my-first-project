import sys
import os
sys.path.append(os.getcwd())
from expense_agent.agent import scrub_personal_data

print(scrub_personal_data("my ssn is 123-45-6789 and cc is 1111-2222-3333-4444"))
