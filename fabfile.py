import os

import yaml
from fabric.contrib.files import upload_template
from fabric.api import *
from pkg_resources import require
import requests
from fabtools import postgres

SLACK_DEPLOYMENT_CHANNEL = 'https://hooks.slack.com/services/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'
SLACK_DEPLOYMENT_DEV_CHANNEL = 'https://hooks.slack.com/services/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'
SLACK_API_TOKEN = 'xoxp-4823337026-8692199938-15293945108-7f812b15bc'
env.local_user = env.user
conf_file = os.path.join(os.environ["HOME"], 'Projects/conf/azure-sentry.yml')
with open(conf_file) as f:
    env.settings = yaml.load(f)

users_json = {
    'Yftahp': 'U04QV75S3',
    'idanshasha': 'U054WTD28',
    'ormeirov': 'U04Q79X1J',
    'darbentov': 'U08LC5VTL'
}


def get_slack_profile_image(user):
    user_id = users_json[user]
    post_data = {
        'token': SLACK_API_TOKEN
    }
    py_reqeust = requests.post('https://slack.com/api/users.list', post_data)
    response_json = py_reqeust.json()
    for member in response_json['members']:
        if member['id'] == user_id:
            return member['profile']['image_192']


def send_to_slack(message, color="#689"):
    web_hook_url = env.slack_url
    machine_text = env.machine
    try:
        thumb_image = get_slack_profile_image(env.local_user)
    except:
        thumb_image = None
    if len(env.hosts) > 1:
        machine_text = '{0} {1}'.format(env.machine, env.hosts.index(env.host) + 1)
    data = {
        "attachments": [
            {
                "fallback": message,
                "text": message,
                "fields": [
                    # {
                    #     "title": "User",
                    #     "value": env.local_user,
                    #     "short": True
                    # },
                    {
                        "title": "Branch",
                        "value": env.branch if hasattr(env, 'branch') else None,
                        "short": True
                    },
                    {
                        "title": "Machine",
                        "value": machine_text,
                        "short": True
                    },
                    {
                        "title": "Environment",
                        "value": env.environment,
                        "short": True
                    },
                    {
                        "title": "Host",
                        "value": env.host,
                        "short": True
                    }
                ],
                "color": color,
                "thumb_url": thumb_image
            }
        ]
    }
    req = requests.post(web_hook_url, json=data)
    return req.content


class CommandFailed(Exception):
    def __init__(self, message, result):
        message = 'Deployment Failed:\n {0}\n{1}'.format(message, result.stdout)
        # send_to_slack(message, color="#FF0000")
        Exception.__init__(self, message)
        self.result = result


def staging():
    env.user = env.settings.get('user_name')
    env.environment = 'staging'
    env.hosts = [env.settings.get('sentry').get('server')]
    env.slack_url = SLACK_DEPLOYMENT_DEV_CHANNEL
    env.key_filename = '~/Projects/Keys/cert.pem'


def run_and_catch_error(*args, **kwargs):
    with warn_only():
        result = run(*args, **kwargs)
    if result.failed:
        raise CommandFailed('commands: {0}'.format(args[0]), result)
    return result


def install_common_packages():
    run('sudo apt-get update')
    run('sudo apt-get install -y build-essential python python-setuptools python-dev libxslt1-dev libxml2-dev libz-dev')
    run('sudo apt-get install -y libffi-dev libssl-dev python-psycopg2 python-pip memcached')
    run('sudo apt-get install -y redis-server')
    run('sudo pip install virtualenvwrapper -U')


def init_nginx():
    with open('settings/nginx.yml', 'r') as yaml_stream:
        settings = yaml.load(yaml_stream)
    run('sudo apt-get install -y python-selinux nginx')
    with warn_only():
        run('sudo mkdir sites-enabled')
        run('sudo mkdir sites-available')
    upload_template('templates/nginx/nginx.conf.j2', '/etc/nginx/nginx.conf', settings, use_jinja=True, use_sudo=True)
    # upload_template('templates/nginx/default.conf.j2', '/etc/nginx/conf.d/default.conf', settings, use_jinja=True, use_sudo=True)
    # upload_template('templates/nginx/default.j2', '/etc/nginx/sites-available/default', settings, use_jinja=True, use_sudo=True)
    # run('sudo ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default')
    run('sudo service nginx restart')


def create_virtualenv():
    """ setup virtualenv on remote host """
    # ===========================================================================
    run_and_catch_error('export WORKON_HOME=~/Envs')
    run_and_catch_error('mkdir -p ~/Envs')  # $WORKON_HOME')
    with prefix('source /usr/local/bin/virtualenvwrapper.sh'):
        run_and_catch_error('mkvirtualenv sentry')
        # ===========================================================================
        # args = '--clear --distribute'


def update_requirements():
    """ update external dependencies on remote host """
    with open('requirements.txt', 'r') as f:
        requirements = ' '.join(f.read().splitlines())
    with prefix('source /usr/local/bin/virtualenvwrapper.sh'):
        with prefix('workon sentry'):
            run_and_catch_error('pip install {}'.format(requirements))


def init_sentry(sentry_settings=None):
    if not sentry_settings:
        sentry_settings = env.settings
    with warn_only():
        run('sudo mkdir -p /www/sentry')
        run('sudo mkdir -p /var/sentry')
    run('sudo ln -snf ~/.virtualenvs/sentry /var/sentry/ve')
    upload_template('templates/sentry/sentry.conf.py.j2', '/var/sentry/sentry_conf.py', sentry_settings, use_sudo=True,
                    use_jinja=True)
    upload_template('templates/sentry/nginx-sentry.conf.j2', '/etc/nginx/sites-available/sentry.conf', sentry_settings,
                    use_sudo=True, use_jinja=True)
    run('sudo chown www-data:www-data /etc/nginx/sites-available/sentry.conf')
    run('sudo ln -fs /etc/nginx/sites-available/sentry.conf /etc/nginx/sites-enabled/sentry.conf')
    upload_template('templates/sentry/supervisor-sentry.conf.j2', '/etc/supervisor/conf.d/sentry.conf', sentry_settings,
                    use_sudo=True, use_jinja=True)
    run('/var/sentry/ve/bin/sentry --config=/var/sentry/sentry_conf.py upgrade --noinput')
    with prefix('source /usr/local/bin/virtualenvwrapper.sh'):
        with prefix('workon sentry'):
            run("""
            export SENTRY_CONF=/var/sentry/sentry_conf.py &&
             python -c "from sentry.utils.runner import configure; configure(); from django.db import DEFAULT_DB_ALIAS as database; from sentry.models import User; User.objects.db_manager(database).create_superuser('{0}', '{1}', '{2}')" executable=/bin/bash chdir=/var/sentry""".format(
                    sentry_settings.get('superuser_sentry', {}).get('username'),
                    sentry_settings.get('superuser_sentry', {}).get('email'),
                    sentry_settings.get('superuser_sentry', {}).get('password', {}))
            )
    run('sudo service nginx restart && killall supervisord && sudo supervisord')


def init_postgres():
    run('sudo apt-get install -y postgresql postgresql-contrib postgresql-client libpq-dev')
    postgres_settings = env.settings.get('db_sentry', {})
    postgres.create_database(name=postgres_settings.get('name'), owner='postgres')
    postgres.create_user(name=postgres_settings.get('user'), password=postgres_settings.get('password'), createdb=True,
                         superuser=True)


def init_supervisor():
    run('sudo apt-get -y install supervisor')
    with warn_only():
        run('sudo mkdir -p /etc/supervisor/conf.d')
        run('sudo mkdir -p /var/log/supervisor')
        put('files/supervisord.conf', '/etc/supervisord.conf', use_sudo=True)


def bootstrap():
    install_common_packages()
    create_virtualenv()
    update_requirements()
    init_postgres()
    init_supervisor()
    init_nginx()
    init_sentry()
