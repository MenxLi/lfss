from lfss.client import upload_directory, Connector

if __name__ == "__main__":
    connector = Connector()
    upload_directory(connector, '.storage_data', 'test/upload_dir/', verbose=True, n_concurrent=4, overwrite=True)