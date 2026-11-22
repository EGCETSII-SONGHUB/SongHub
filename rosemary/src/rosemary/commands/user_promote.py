import click
from flask.cli import with_appcontext


@click.command("user:promote", help="Sets the role of an existing user (default: admin).")
@click.argument("email")
@click.option("--role", type=click.Choice(["admin", "curator", "user"]), default="admin", show_default=True)
@with_appcontext
def user_promote(email, role):
    # Imported lazily: importing `app` builds the Flask app.
    from app.features.auth.services import AuthenticationService

    service = AuthenticationService()
    user = service.repository.get_by_email(email)
    if user is None:
        raise click.ClickException(f"No user with email {email}")
    try:
        service.change_role(user, role)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    click.echo(click.style(f"{email} is now {role}.", fg="green"))