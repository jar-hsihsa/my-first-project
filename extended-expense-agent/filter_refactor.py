import re

with open('frontend/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove Top "My Expense History" block
top_table_pattern = r"    # ── My Expense History ───────────────────────────────────.*?st\.markdown\(\"---\"\)\n\n"
content = re.sub(top_table_pattern, "", content, flags=re.DOTALL)

# 2. Refactor bottom "My Expenses Table" to include filtering
bottom_employee_table = r"""    # ── My Expenses Table ────────────────────────────────────
    my_expenses = get_employee_expenses\(st\.session_state\.email\)
    if my_expenses:.*?unsafe_allow_html=True,
        \)"""

filtered_employee_table = """    # ── My Expenses Table ────────────────────────────────────
    my_expenses = get_employee_expenses(st.session_state.email)
    if my_expenses:
        st.markdown(
            f'<div class="section-title" style="margin-top:2rem;">My Expenses</div>',
            unsafe_allow_html=True,
        )
        
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            emp_search = st.text_input("Search (ID, Description)", key="emp_search").lower()
        with col_f2:
            emp_cat_filter = st.multiselect("Category", options=list(set(e.get("category", "") for e in my_expenses if e.get("category"))), key="emp_cat")
        with col_f3:
            emp_status_filter = st.multiselect("Status", options=["Approved", "Auto-Approved", "Rejected", "Awaiting Approval"], key="emp_status")

        filtered_expenses = []
        for exp in my_expenses:
            exp_id = f"EX{exp.get('id', 0):04d}"
            status = exp.get("status", "Approved")
            cat = exp.get("category", "")
            desc = exp.get("description", "")
            
            # Apply filters
            if emp_search and emp_search not in exp_id.lower() and emp_search not in desc.lower(): continue
            if emp_cat_filter and cat not in emp_cat_filter: continue
            if emp_status_filter and status not in emp_status_filter: continue
                
            filtered_expenses.append(exp)

        rows_html = ""
        for exp in filtered_expenses:
            exp_id = f"EX{exp.get('id', 0):04d}"
            status = exp.get("status", "Approved")
            status_cls = "status-approved" if status == "Approved" else ("status-auto-approved" if status == "Auto-Approved" else ("status-rejected" if status == "Rejected" else "status-awaiting"))
            rows_html += f\"\"\"<tr>
                <td><strong>{exp_id}</strong></td>
                <td>{exp.get('date','—')}</td>
                <td>{exp.get('category','—')}</td>
                <td><strong>${exp.get('amount',0):.2f}</strong></td>
                <td>{exp.get('description','—')[:40]}</td>
                <td><span class="status-badge {status_cls}">{status}</span></td>
            </tr>\"\"\"

        st.markdown(
            f\"\"\"<table class="expense-table">
                <thead><tr>
                    <th>Expense ID</th><th>Date</th>
                    <th>Category</th><th>Amount</th><th>Description</th><th>Status</th>
                </tr></thead>
                <tbody>{rows_html}</tbody>
            </table>\"\"\",
            unsafe_allow_html=True,
        )
    else:
        st.info("No past expenses found for your account.")
"""
content = re.sub(bottom_employee_table, filtered_employee_table, content, flags=re.DOTALL)

# 3. Refactor Admin "All Expenses" table to include filtering
admin_table = r"""    # ── All expenses table \(always visible for admin\) ────────
    if all_expenses:
        st\.markdown\(
            f'<div class="section-title" style="margin-top:1rem;">All Expenses \(\{len\(all_expenses\)\}\)</div>',.*?unsafe_allow_html=True,
        \)"""

filtered_admin_table = """    # ── All expenses table (always visible for admin) ────────
    if all_expenses:
        st.markdown(
            f'<div class="section-title" style="margin-top:1rem;">All Expenses</div>',
            unsafe_allow_html=True,
        )

        col_a1, col_a2, col_a3 = st.columns(3)
        with col_a1:
            adm_search = st.text_input("Search (ID, Description, Employee)", key="adm_search").lower()
        with col_a2:
            adm_cat_filter = st.multiselect("Category", options=list(set(e.get("category", "") for e in all_expenses if e.get("category"))), key="adm_cat")
        with col_a3:
            adm_status_filter = st.multiselect("Status", options=["Approved", "Auto-Approved", "Rejected", "Awaiting Approval"], key="adm_status")

        filtered_admin_expenses = []
        for exp in all_expenses:
            exp_id = f"EX{exp.get('id', 0):04d}"
            status = exp.get("status", "Approved")
            cat = exp.get("category", "")
            desc = exp.get("description", "")
            emp_email = exp.get("submitter", "").lower()
            emp_name = _display_name(exp.get("submitter", "")).lower()
            
            # Apply filters
            if adm_search and (adm_search not in exp_id.lower() and adm_search not in desc.lower() and adm_search not in emp_email and adm_search not in emp_name): continue
            if adm_cat_filter and cat not in adm_cat_filter: continue
            if adm_status_filter and status not in adm_status_filter: continue
                
            filtered_admin_expenses.append(exp)

        rows_html = ""
        for exp in filtered_admin_expenses:
            exp_id = f"EX{exp.get('id', 0):04d}"
            emp_init = _initials(exp.get("submitter", ""))
            emp_name = _display_name(exp.get("submitter", ""))
            status = exp.get("status", "Approved")
            status_cls = "status-approved" if status == "Approved" else ("status-auto-approved" if status == "Auto-Approved" else ("status-rejected" if status == "Rejected" else "status-awaiting"))
            rows_html += f\"\"\"<tr>
                <td><strong>{exp_id}</strong></td>
                <td>
                    <div class="emp-chip">
                        <span class="emp-avatar">{emp_init}</span>
                        <div>
                            <div class="emp-name">{emp_name}</div>
                        </div>
                    </div>
                </td>
                <td>{exp.get('date','—')}</td>
                <td>{exp.get('category','—')}</td>
                <td><strong>${exp.get('amount',0):.2f}</strong></td>
                <td>{exp.get('description','—')[:40]}</td>
                <td><span class="status-badge {status_cls}">{status}</span></td>
            </tr>\"\"\"

        st.markdown(
            f\"\"\"<table class="expense-table">
                <thead><tr>
                    <th>Expense ID</th><th>Employee</th><th>Date</th>
                    <th>Category</th><th>Amount</th><th>Description</th><th>Status</th>
                </tr></thead>
                <tbody>{rows_html}</tbody>
            </table>\"\"\",
            unsafe_allow_html=True,
        )"""

content = re.sub(admin_table, filtered_admin_table, content, flags=re.DOTALL)


with open('frontend/app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Filters and table cleanup applied.")
