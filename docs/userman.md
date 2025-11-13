# User Management

All user management operations can be performed via the `lfss-user` command. 
Using `-h` or `--help` flag will show the help message with all available subcommands and options:
```bash
> lfss-user -h                                                     
usage: lfss-user [-h] {add,add-virtual,delete,set,list,set-peer,set-expire} ...

positional arguments:
  {add,add-virtual,delete,set,list,set-peer,set-expire}
    add                 Add a new user
    add-virtual         Add a virtual (hidden) user, username will be prefixed with '.v-'
    set                 Set user properties, refer to 'add' subcommand for details on each argument
    list                List specified users, or detailed info with -l
    set-peer            Set peer user relationship
    set-expire          Set or clear user expire time
```

Most of the commands are self-explanatory, 
and the details flags of each command can be found by using the `-h` flag after the subcommand. 

**Below are some extra explanations for a few commands.**

## Check user details
Besides listing all users, 
to check the details of the user(s), you can also use the `list` subcommand with the `-l/--long` flag, 
followed by one or more usernames. For example:
```bash
> lfss-user list -l alice
User alice (id=20, admin=0, created at 2025-11-13 03:15:09, last active at 2025-11-13 03:15:09, storage=1.00G, permission=UNSET)
- Credential:  d9cf3312d1da59721fd28a5d3075c65b858a373d37e479c2defd6bfeee207677
- Storage: 0B / 1.00G
- Expire: never
- Peers [READ]: bob, carol
- Peers [WRITE]: dave
```

## Delete user
To delete a user, you can use the `delete` subcommand.
```bash
> lfss-user delete alice
```

Note: there are a few clean up operations that need to be done when deleting a user, 
so the deletion process may take some time depending on the number of files owned by the user, 
and because this process is transactional, it may block the system for a short period.

Specifically, user deletion involves:
- Remove user record from the database.
- Remove all files under the user's path.
- Transfer ownership of all files owned by the user under other users' paths to the path owner.

If any of the above steps fail 
(for example, the path owner has insufficient storage space to take over the ownership), 
the deletion process will be rolled back to ensure data consistency.
