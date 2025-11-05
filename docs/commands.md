# CLI Commands

## Client Commands
If you install LFSS via pip, you will get the `lfss` command-line tool.

```bash
lfss --help
```

The `lfss` command is the client tool to interact with the LFSS server, it has various subcommands, please check the help message for more details. 


## Server Commands
If you install LFSS via pip with `[all]` option, you will get other commands starting with `lfss-`.

```bash
lfss-serve          # Start the LFSS server
lfss-user           # Manage users
lfss-log            # View server logs
lfss-vacuum         # Vacuum the database and shrink log files
```

All these commands have their own `--help` message, you can check them for more details.



