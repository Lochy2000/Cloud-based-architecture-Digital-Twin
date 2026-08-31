# TLS setup for the self-hosted broker (C1)

Self-signed certificates are generated so that Mosquitto accepts encrypted connections on port 8883.

TLS is enabled on the self-hosted broker because both managed brokers mandate it. Without it, an encrypted service would be compared against an unencrypted one, and the additional setup effort would not be counted in the deployment complexity measurements. Self-signed certificates are used rather than Let's Encrypt because no public domain name is available and the deployment is a controlled experiment rather than a production service. This simplification is stated in the write-up.

The commands below are run on whichever machine hosts the broker: initially a local development machine for testing, and subsequently the cloud VM for the measured run. Certificates are bound to a hostname, so they are regenerated on the VM. No software is installed; the commands generate files in a single directory.

## Certificate generation

From the repository root:

```bash
cd deploy/mosquitto
mkdir -p certs && cd certs
```

### 1. Certificate authority

```bash
openssl req -new -x509 -days 365 -extensions v3_ca \
  -keyout ca.key -out ca.crt -nodes \
  -subj "/C=GB/ST=London/O=DigitalTwinProject/CN=DigitalTwinCA"
```

The `-nodes` flag omits passphrase protection on the private key. Without it, the broker would require interactive input at every container start.

### 2. Server key and signing request

```bash
openssl req -new -newkey rsa:2048 -nodes \
  -keyout server.key -out server.csr \
  -subj "/C=GB/ST=London/O=DigitalTwinProject/CN=mosquitto"
```

The common name `mosquitto` matches the service name in `docker-compose.yml`, which is the hostname the clients connect to. It differs from the authority's common name to avoid a self-signing conflict.

### 3. Subject alternative names

```bash
cat > san.cnf << 'EOF'
subjectAltName = DNS:mosquitto,DNS:localhost,IP:127.0.0.1
EOF
```

Current TLS clients validate the hostname against the subject alternative name list rather than the common name. Omitting this step produces a certificate that fails validation. The `localhost` and IP entries permit testing from the host machine as well as from within Docker.

### 4. Signing

```bash
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -days 365 -extfile san.cnf
```

### 5. Verification

```bash
openssl verify -CAfile ca.crt server.crt
```

The expected output is `server.crt: OK`. The alternative names are confirmed with:

```bash
openssl x509 -in server.crt -noout -text | grep -A1 "Subject Alternative Name"
```

### 6. Key permissions

```bash
chmod 600 ca.key server.key
```

Mosquitto refuses to start if key files are world-readable.

## Generated files

| File | Purpose |
|---|---|
| `ca.crt` | Used by the broker; required by the publisher and storage writer to trust it |
| `ca.key` | Signs certificates; retained and not distributed |
| `server.crt` | Broker certificate |
| `server.key` | Broker private key |
| `server.csr` | Intermediate file, used only during generation |
| `san.cnf` | Intermediate file |
| `ca.srl` | Serial number tracker created by OpenSSL |

All files remain in `deploy/mosquitto/certs/`. The repository's `.gitignore` excludes `*.crt`, `*.key` and `*.pem`, so private keys are never committed. Consequently the files exist only on the machine that generated them.

## Password file

Anonymous access is disabled in the broker configuration, so a password file is required. The tool is available inside the Mosquitto image, avoiding a local installation:

```bash
cd deploy/mosquitto
docker run --rm -it -v "$PWD:/work" eclipse-mosquitto:2.1.2-alpine \
  mosquitto_passwd -c /work/passwd twin
```

The password entered is recorded in `BROKER_PASSWORD` in the environment file. The `-c` flag creates a new file and overwrites any existing one.

## Related changes

The client configuration requires the certificate authority path. In `config/env/c1.env`:

```bash
BROKER_CA_CERT=/certs/ca.crt
```

In `src/twin/mqtt_client.py`, the password authentication branch passes no certificate authority to `tls_set()`, causing it to fall back to the system trust store, which does not recognise the generated authority:

```python
if config.auth_mode == "password":
    client.username_pw_set(config.username, config.password)
    if config.tls:
        client.tls_set(ca_certs=config.ca_cert, tls_version=ssl.PROTOCOL_TLSv1_2)
```

For HiveMQ Cloud, `config.ca_cert` is `None` and the system trust store is used, which is correct because that certificate is publicly trusted. The corresponding unit test is updated to assert the certificate authority path is passed through.

## Testing

The broker is started in isolation:

```bash
cd deploy
docker compose --profile c1 up mosquitto
```

A subscription is opened from a second terminal:

```bash
mosquitto_sub -h localhost -p 8883 \
  --cafile deploy/mosquitto/certs/ca.crt \
  -u twin -P <password> \
  -t 'twin/#' -v
```

And a message published:

```bash
mosquitto_pub -h localhost -p 8883 \
  --cafile deploy/mosquitto/certs/ca.crt \
  -u twin -P <password> \
  -t 'twin/test' -m 'hello'
```

Receipt of the message at the subscriber confirms both encryption and authentication.

## Common failures

| Symptom | Cause |
|---|---|
| `unable to get local issuer certificate` | The client is not using the generated authority certificate; check `BROKER_CA_CERT` and the volume mount |
| Hostname mismatch | The connection hostname is absent from the subject alternative names; verify step 3 |
| Broker fails to start, key permission error | `chmod 600` was not applied |

Certificates are valid for 365 days. Rotation is ongoing operational work for the self-hosted configuration that does not apply to the managed brokers. A 24-hour run does not surface this, so it is addressed qualitatively in the maintainability discussion.

## Sources

- [Mosquitto configuration reference](https://mosquitto.org/man/mosquitto-conf-5.html) — `cafile`, `certfile` and `keyfile` directives
- [`mosquitto_passwd` manual](https://mosquitto.org/man/mosquitto_passwd-1.html)
- [Cedalo, MQTT TLS/SSL configuration guide](https://www.cedalo.com/blog/mqtt-tls-configuration-guide)
- [Steve's Internet Guide, Mosquitto TLS](http://www.steves-internet-guide.com/mosquitto-tls/)
- [OpenSSL `req` manual](https://docs.openssl.org/master/man1/openssl-req/) and [`x509` manual](https://docs.openssl.org/master/man1/openssl-x509/)
- [eclipse-mosquitto on Docker Hub](https://hub.docker.com/_/eclipse-mosquitto)

Several published guides set `require_certificate true`, which requires clients to present their own certificate. This configuration omits it, as username and password authentication is used instead. Client certificate authentication is the mechanism used by AWS IoT Core, which is a genuine difference between the configurations.
