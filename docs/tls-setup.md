# C1 TLS setup

The local Mosquitto deployment uses TLS and password authentication so it is
comparable with managed broker configurations.

## Required artifacts

Place these generated files under `deploy/mosquitto/certs`:

| File | Use |
| --- | --- |
| `ca.crt` | Trust anchor mounted into broker clients. |
| `server.crt` | Mosquitto server certificate. |
| `server.key` | Mosquitto private key. |

The server certificate must be signed by `ca.crt` and contain
`DNS:mosquitto` in its Subject Alternative Name. Add `DNS:localhost` when the
broker will also be accessed from the host. A one-year certificate is adequate
for local experiments; production deployments require managed rotation.

Use OpenSSL or an organisational PKI to create the CA and signed server
certificate. Verify the result:

```powershell
openssl verify -CAfile ca.crt server.crt
openssl x509 -in server.crt -noout -subject -issuer -dates -ext subjectAltName
```

Expected chain output is `server.crt: OK`.

## Password database

Create `deploy/mosquitto/passwd` with the `mosquitto_passwd` utility from the
Mosquitto image. The configured username is `twin`; its password must equal
`BROKER_PASSWORD` in the runtime environment file.

The result must be a non-empty file, not a directory, and must be readable by
the `mosquitto` user inside the container. The file contains a password hash but
must still remain outside version control.

Set the client trust path in C1:

```env
BROKER_CA_CERT=/certs/ca.crt
```

See [operations.md](operations.md#troubleshooting) for common failures and the
[Mosquitto TLS configuration reference](https://mosquitto.org/man/mosquitto-tls-7.html)
for certificate details.
