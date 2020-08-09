import sys
import os
import os.path
from flask import Flask
from flask_s3_viewer import FlaskS3Viewer
from flask_s3_viewer.aws.ref import Region

import subprocess
from os import remove
import sys

if os.getenv("NB_PREFIX"):
    PREFIX = os.getenv("NB_PREFIX")
else:
    PREFIX = ""

app = Flask(__name__)

#app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if PREFIX:
    from flask import url_for, send_from_directory
    from flask_reverse_proxy_fix.middleware import ReverseProxyPrefixFix
    app.config['REVERSE_PROXY_PATH'] = PREFIX + '/proxy/8765'
    ReverseProxyPrefixFix(app)


def _get_minio_client(tenant):
    """ Get the variables out of vault to create Minio Client. """

    d = {
        'MINIO_URL'        : None,
        'MINIO_ACCESS_KEY' : None,
        'MINIO_SECRET_KEY' : None
    }

    if tenant not in ("minimal", "premium", "pachyderm"):
        print("Not a valid resource! Options are")
        print("minimal, premium, pachyderm.")
        print("We will try anyway...")

    vault = f"/vault/secrets/minio-{tenant}-tenant1"

    for var in d: 
        CMD = f'echo $(source {vault}; echo ${var})'
        p = subprocess.Popen(CMD, stdout=subprocess.PIPE, shell=True,
                             executable='/bin/bash')
        d[var] = p.stdout.readlines()[0].strip().decode("utf-8")

    return d

def get_minimal_client():
    """Get a connection to the minimal Minio tenant"""
    return __get_minio_client__("minimal")

def get_pachyderm_client():    
    """Get a connection to the pachyderm Minio tenant"""
    return __get_minio_client__("pachyderm")

def get_premium_client():
    """Get a connection to the premium Minio tenant"""
    return __get_minio_client__("premium")


if len(sys.argv) > 1:
    tenant = sys.argv[0]
else:
    tenant = "minimal"

d = _get_minio_client(tenant)


NB_PREFIX = os.getenv("NB_PREFIX") + '/proxy/8765'
BUCKET = os.getenv("NB_PREFIX").split('/')[2]

app.config['DOWNLOAD_DIR'] = os.path.join(os.getenv("HOME"), "downloads")

creds_dir = os.path.join(os.getenv("HOME"), ".aws")
os.makedirs(creds_dir, exist_ok=True)

# These don't have to be correct!! Anything works.
with open(creds_dir + "/credentials", "w") as f:
    f.write("""
[minio]
aws_access_key_id=minioadmin
aws_secret_access_key=minioadmin
region = us-east-1
""")

# # For test, disable template caching
# app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 1
# app.config['TEMPLATES_AUTO_RELOAD'] = True

# FlaskS3Viewer Init
s3viewer = FlaskS3Viewer(
    app, # Flask app
    namespace=BUCKET, # namespace be unique
    template_namespace='mdl', # set template
    object_hostname='http://flask-s3-viewer.com', # file's hostname
    allowed_extensions={}, # allowed extension
    config={ # Bucket configs and else
        'profile_name': 'minio',
        'access_key': d['MINIO_ACCESS_KEY'],
        'secret_key': d['MINIO_SECRET_KEY'],
        'region_name': Region.SEOUL.value,
        'endpoint_url': d['MINIO_URL'],
        'bucket_name': BUCKET,
        'use_ssl': False,
        'cache_dir': '/tmp/flask_s3_viewer',
        'use_cache': False,
        'ttl': 86400
    }
)

# Init another one
s3viewer.add_new_one(
    namespace='shared',
    template_namespace='mdl', # set template
    object_hostname='http://example.com',
    config={
        'profile_name': 'minio',
        'access_key': d['MINIO_ACCESS_KEY'],
        'secret_key': d['MINIO_SECRET_KEY'],
        'endpoint_url': d["MINIO_URL"],
        'bucket_name': 'shared',
        'use_ssl': False,
        'region_name': Region.SEOUL.value
    }
)

# You can see registerd configs
# print(s3viewer.FLASK_S3_VIEWER_BUCKET_CONFIGS)

# You can use boto3's session and client if you want
# print(FlaskS3Viewer.get_boto_client(FS3V_NAMESPACE))
# print(FlaskS3Viewer.get_boto_session(FS3V_NAMESPACE))

# Apply FlaskS3Viewer blueprint
s3viewer.register()

@app.route('/')
def index ():
    return f"""
This is the root of the storage explorer! We will add a nice splash page later.

You probably want to go to one of these:

<ul>
<li><a href="{NB_PREFIX}/{BUCKET}/files">{BUCKET}</a></li>
<li><a href="{NB_PREFIX}/shared/files">Shared</a></li>
</ul>
"""

print(f"""

Thanks for using the DAaaS Jupyter Storage System! Go to 

https://kubeflow.covid.cloud.statcan.ca{NB_PREFIX}

""")

# Usage: python example.py test (run debug mode)
if __name__ == '__main__':
    debug = False
    if len(sys.argv) > 1:
        if sys.argv[1] == 'test':
            debug = True
    app.run(debug=debug, port=8765)

