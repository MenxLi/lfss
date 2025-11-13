# Virtual User

> Added in v0.16.0.

Virtual user is a user without its own path. 
It can only access files and directories under other users' paths according to the peer user settings, 
and anybody want to access virtual user's path will get permission denied.

In addition, virtual users is preferred to have an expiry time, after which they can no longer access the system. 
This makes virtual users essentially "access keys" to some users' paths.

The virtual user always have a name starting with `.v-`, 
a typical virtual user name looks like `.v-{tag}-{id}`. 
The tag is used to identify the purpose of the virtual user, and the id is a unique random string.

To create a virtual user, you can use either the CLI command or the admin API. For example:

```bash
lfss-user add-virtual 
    --tag tmpuser 
    --expire 1d12h 
    --max-storage 100M
    --peers "read:alice,bob;write:carol"
```

```python
Client().add_virtual_user(
    tag="tmpuser",
    expire="1d12h",
    max_storage="100M",
    peers={
        AccessLevel.READ: ["alice", "bob"], 
        AccessLevel.WRITE: ["carol"]
    }
)
```

To modify the expiry time of a virtual user, you can use the CLI command. For example:
```bash
lfss-user set-expire .v-tmpuser-VwFdjKpiqm4 2d1h10s
```

The management of virtual users is exactly the same as normal users. *e.g.*, via `lfss-user` command or admin API.

