# Security Guidelines

This document outlines security best practices for this project.

## 🔐 API Key Management

### Local Development

1. **Never commit your real API keys** to the repository
2. Create a `.env` file in the project root (already in `.gitignore`)
3. Add your Gemini API key:
   ```env
   GEMINI_API_KEY=your_actual_api_key_here
   ```
4. The `.env` file is automatically loaded by `dotenv` in `index.js`

### Production Deployment

For production deployments, use secure secrets management:

- **GitHub**: Use [GitHub Actions Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- **Google Cloud**: Use [Google Cloud Secret Manager](https://cloud.google.com/secret-manager/docs)
- **Environment Variables**: Set credentials via environment variables in your deployment platform

Example for GitHub Actions:
```yaml
- name: Run script
  env:
    GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
  run: node index.js
```

## ⚠️ What NOT to Do

- ❌ Hardcode API keys in code
- ❌ Commit `.env` file with real credentials
- ❌ Share API keys in chat, email, or pull requests
- ❌ Use API keys in version control history (check with `git log`)

## 🛠️ Detecting Secret Leaks

### Check Git History

If you accidentally committed a secret, check the history:

```bash
git log --all --full-history -- .env | head -20
```

### Using detect-secrets

Install and run [detect-secrets](https://github.com/Yelp/detect-secrets) to scan for secrets:

```bash
pip install detect-secrets
detect-secrets scan
```

### GitHub Secret Scanning

If using GitHub, enable [Secret Scanning](https://docs.github.com/en/code-security/secret-scanning) to automatically detect committed secrets.

## 📋 If You Accidentally Leaked a Secret

1. **Immediately rotate the credential** (e.g., regenerate your Gemini API key)
2. **Remove from history** using:
   ```bash
   git filter-branch --tree-filter 'rm -f .env' -- --all
   git push --force-with-lease
   ```
3. **Force push** to update the remote repository
4. **Notify team members** if it's a shared project

## 🔍 Regular Security Audits

- Review `.gitignore` to ensure secrets patterns are covered
- Use `git ls-files` to check what's tracked:
  ```bash
  git ls-files | grep -E '\.(env|key|pem|secret)' || echo "✓ No secrets in git"
  ```
- Enable GitHub's Dependabot for dependency vulnerability scanning

## 📚 References

- [OWASP: Secrets Management](https://owasp.org/www-community/attacks/Sensitive_Data_Exposure)
- [GitHub: Protecting Sensitive Data](https://docs.github.com/en/code-security/secret-scanning)
- [Google Cloud: Secret Manager Best Practices](https://cloud.google.com/secret-manager/docs/best-practices)
