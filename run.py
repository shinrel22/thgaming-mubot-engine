import click
import asyncio
from src.constants.trainer import DEFAULT_PORT
from src.trainers import Trainer
from src.utils import capture_error


@click.group()
def cli():
    pass


@cli.command(short_help='Run the trainer')
@click.option('--rsp', default=DEFAULT_PORT, help='Port for the restful server')
@click.option('--wsp', default=DEFAULT_PORT + 1, help='Port for the websocket server')
@click.option('--ui-origin', default='http://localhost:8080', help='UI origin to be allowed to connect to')
def run(**kwargs):

    ui_origin = kwargs['ui_origin']
    restful_server_port = int(kwargs['rsp'])
    websocket_server_port = int(kwargs['wsp'])

    print('ui_origin', ui_origin)
    print('restful_server_port', restful_server_port)
    print('websocket_server_port', websocket_server_port)

    trainer = Trainer(
        restful_server_port=restful_server_port,
        websocket_server_port=websocket_server_port,
        ui_origin=ui_origin,
    )

    return asyncio.run(trainer.run())


if __name__ == '__main__':
    try:
        run()
    except Exception as e:
        capture_error(e)
        raise e
