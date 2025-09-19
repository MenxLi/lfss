
# Client-side CLI tools

To install python CLI tools without dependencies (to avoid conflicts with your existing packages):
```sh
pip install requests
pip install lfss --no-deps
```

Then set the `LFSS_ENDPOINT`, `LFSS_TOKEN` environment variables, 
then you can use the following commands:
```sh
# Query a path
lfss query remote/file[/or_dir/]

# List directories of a specified path
lfss list-dirs remote/dir/

# List files of a specified path, 
# with pagination and sorting
lfss list-files --offset 0 --limit 100 --order access_time remote/dir/

# Upload a file
lfss upload local/file.txt remote/file.txt

# Upload a directory, note the ending slashes
lfss upload local/dir/ remote/dir/

# Download a file
lfss download remote/file.txt local/file.txt

# Download a directory, with verbose output and 8 concurrent jobs
# Overwrite existing files
lfss download -v -j 8 --conflict overwrite remote/dir/ local/dir/   
```

More commands can be found using `lfss-cli --help`.