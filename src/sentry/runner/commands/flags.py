import click


@click.group()
def flags():
    "Manage Sentry plugins."


@flags.command()
def create():
    "Create a feature flag"
    # plugins = [
    #     (ep.name, dist.metadata["name"], dist.version, str(dist.locate_file(".")))
    #     for dist in importlib.metadata.distributions()
    #     for ep in dist.entry_points
    #     if ep.group == "sentry.plugins"
    # ]
    # plugins.sort()
    # for name, project_name, version, location in plugins:
    #     click.echo(f"{name}: {project_name} {version} ({location})")
