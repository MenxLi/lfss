
# Configure Single Directory

> Added in v0.14.0.

You can configure the behavior of a single directory by placing a special file named `.lfssdir.json` in it.

The file should contain a JSON object with the following optional fields:
- `index`: A string specifying the index file name to serve when a directory is accessed. Such as `"index.html"`.
- `access-control`: An object specifying access control rules for the directory. The keys are usernames, and the values are access levels, which can be `"read"`, `"write"`, or `"none"`.

:::info Note:
1. The settings in `.lfssdir.json` only apply to the directory it is placed in, not its subdirectories. 
2. Only the owner (either the path owner or file owner) or admin can read or modify the `.lfssdir.json` file. 
3. The access control rules in `.lfssdir.json` will override the peer user's access control settings for files in this directory.
:::

An example `.lfssdir.json` file:
```json
{
  "index": "index.html",
  "access-control": {
    "alice": "read",
    "bob": "write",
    "eve": "none"
  }
}
```
This configuration will make the server serve `index.html` when the directory is accessed, allow user `alice` to read files in this directory, allow user `bob` to read and write files, and deny access from user `eve`.

:::info Direct URL Access
If a file has public/protected read access, 
it will still be accessible by the corresponding users if it's accessed by its direct URL, 
regardless of the `.lfssdir.json` settings.
:::
