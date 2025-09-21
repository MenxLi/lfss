
# Client-side CLI tools

To install python CLI tools without dependencies (to avoid conflicts with your existing packages):
```sh
pip install requests
pip install lfss --no-deps
```

Then set the `LFSS_ENDPOINT`, `LFSS_TOKEN` environment variables, 
then you can use the following commands:
```sh
# Check current user information
lfss whoami

# Query a path
lfss i remote/file[/or_dir/]

# List a specified path, 
# with pagination and sorting
lfss ls remote/dir/ --offset 0 --limit 100 --order access_time 

# Upload a file
lfss up local/file.txt remote/file.txt

# Upload a directory, note the ending slashes
lfss up local/dir/ remote/dir/

# Download a file
lfss down remote/file.txt local/file.txt

# Download a directory, with 8 concurrent jobs
# Overwrite existing files
lfss down remote/dir/ local/dir/ -j 8 --conflict overwrite  
```

More commands can be found using `lfss --help`.