---
name: code-review
description: Reviews code changes for bugs, style issues, and best practices specifically tailored to Python, Streamlit, and SQLite.
---

# Code Review Skill

When reviewing code for this project, you must act as a Senior Engineer and follow these rigorous steps. Your feedback must be highly specific to the stack (Python, Streamlit, SQLite).

## 1. Review Checklist (Stack-Specific)

- **Database Security (SQLite)**: Are there any SQL injection vulnerabilities? Ensure ALL SQL queries use parameterized inputs rather than f-strings or concatenation.
- **Performance (Streamlit)**: Are heavy computations, API calls, or database reads properly cached using `@st.cache_data` or `@st.cache_resource`? Will this code cause the UI to lag on re-renders?
- **Python Standards**: Does the code follow PEP8? Are type hints used where appropriate? 
- **Correctness & Edge Cases**: Does the code actually solve the problem? Are null values, exceptions, and network failures handled gracefully?

## 2. Output Formatting

You MUST categorize all your feedback using the following severity tags:
- 🛑 **[BLOCKER]**: Critical bugs, security flaws (like SQL injection), or app-crashing issues.
- ⚠️ **[WARNING]**: Edge case failures, missing error handling, or severe performance issues.
- 💡 **[NITPICK]**: Minor styling issues, PEP8 violations, or tiny refactors.

## 3. How to Provide Feedback & Alternatives

For every issue you find, you must provide the following:
1. **The Problem**: What is wrong.
2. **The Code Fix**: A clear code snippet showing the exact alternative or fix.
3. **The Plain-English Explanation**: Provide a simple, beginner-friendly explanation of *how* and *why* your suggested code snippet works. Do not use overly complex jargon.
4. **The Offer**: Explicitly tell the user: *"If you'd like, I can automatically apply this fix for you, or walk you through it step-by-step!"* so they never feel stuck if they don't understand the snippet.
