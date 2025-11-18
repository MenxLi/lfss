# Start LFSS on Boot with `systemd`

> Added in v0.16.1

Optionally, you can generate a systemd unit file for LFSS server using the following command:
```bash
lfss-systemd
```
This will print the unit file content to stdout.

You can also specify the environment variables for the service, 
as well as the parameter for `lfss-serve` command. 
You should put the output to the global systemd unit directory, e.g.
```bash
export LFSS_DATA="/path/to/data"
export LFSS_ORIGIN="http://localhost:8000,https://mydomain.com"

lfss-systemd --workers 2 | sudo tee /etc/systemd/system/lfss.service
```
Then enable and start the service with:
```bash
sudo systemctl daemon-reload
sudo systemctl enable lfss.service
sudo systemctl start lfss.service
```

To check the log output of the service, you can use `journalctl`:
```bash
sudo journalctl -u lfss.service -f
```