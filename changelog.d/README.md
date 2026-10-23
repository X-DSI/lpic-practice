# Changelog fragments

Each pull request that changes behaviour adds one file here:

```
changelog.d/<slug>.<type>.md
```

`<type>` is one of `added`, `changed`, `fixed`, `removed`, `deprecated`, `security`. The file holds
one or more Markdown bullet points. Fragments are merged into `CHANGELOG.md` and deleted when a
version is tagged.
