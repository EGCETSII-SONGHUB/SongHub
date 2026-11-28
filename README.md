<div style="text-align: center;">
  <img src="https://www.uvlhub.io/static/img/logos/logo-light.svg" alt="Logo">
</div>

# uvlhub.io

Repository of feature models in UVL format integrated with Zenodo and flamapy following Open Science principles - Developed by DiversoLab.

## Official documentation

You can consult the official documentation of the project at [docs.uvlhub.io](https://docs.uvlhub.io/)

## Email delivery and verification

New accounts receive a welcome message with a signed email-verification link
and must verify their address before uploading datasets. Links expire after one
hour by default; override this with `EMAIL_VERIFICATION_MAX_AGE` (seconds).

Development uses Mailpit instead of delivering messages to real addresses. Start
it with `docker compose -f docker/docker-compose.dev.yml up -d mailpit`; view
captured messages at [http://localhost:8025](http://localhost:8025) (SMTP port
1025). The Docker application uses `MAIL_SERVER=mailpit`; a local host process
uses `MAIL_SERVER=localhost`. For Vagrant, start the same Mailpit service on the
host and use `MAIL_SERVER=10.0.2.2` from the guest. The corresponding values
are in the `.env.*.example` files. Run
`MAILPIT_API_URL=http://localhost:8025 pytest app/features/email/tests/test_mailpit.py -m integration`
to send a message and verify it through Mailpit's API.

Production should set `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`,
`MAIL_USERNAME`, `MAIL_PASSWORD`, and `MAIL_DEFAULT_SENDER` to a real SMTP
provider. The reusable `EmailService` sends the registration verification
message and can be used by other features.
