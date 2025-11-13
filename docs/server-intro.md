
# Server Setup Guide

```bash
pip install "lfss[all]"
```

Start the server:
```bash
lfss-serve
```
Now the server is running at `http://localhost:8000`.

By default, the data will be stored in `.storage_data`. 
You can change the storage directory using the `LFSS_DATA` environment variable, 
more details can be found in [Environment variables](./environment-variables.md).

## Create a user
Create a user using the following command:
```bash
lfss-user add <username> <password> --admin
```
This command will create an admin user, which can manage other users. 
More sub commands can be found in `lfss-user --help` and `lfss-user <subcommand> --help`. 
Details on user management can be found in [User Management](./userman.md).

## Interact with the server
Please refer to [Client-side tools](./client-intro.md) for more details on how to use the client CLI tools to interact with the server.