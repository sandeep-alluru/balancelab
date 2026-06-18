# GitHub Action

Use balancelab directly in your GitHub Actions workflow:

```yaml
- name: balancelab
  uses: sandeep-alluru/balancelab@v0.1.0
  with:
    # TODO: add action inputs
    fail-on-error: "true"
```

Or use the CLI directly:

```yaml
- name: Install balancelab
  run: pip install balancelab

- name: Run balancelab
  run: balancelab --help
```
