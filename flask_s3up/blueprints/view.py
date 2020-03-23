import urllib
import unicodedata
import os

from werkzeug.wsgi import FileWrapper
from werkzeug.urls import url_quote
from flask import Response, request, render_template, Blueprint, g, abort
from .. import FlaskS3Up, FLASK_S3UP_NAMESPACE

blueprint = Blueprint(
    FLASK_S3UP_NAMESPACE,
    __name__,
    template_folder=f'./{FLASK_S3UP_NAMESPACE}/templates/{FLASK_S3UP_NAMESPACE}',
    static_folder='static',
    url_prefix='/<path:FLASK_S3UP_BUCKET_NAMESPACE>'
)

@blueprint.url_defaults
def add_division(endpoint, values):
    values.setdefault('FLASK_S3UP_BUCKET_NAMESPACE', g.FLASK_S3UP_BUCKET_NAMESPACE)

@blueprint.url_value_preprocessor
def pull_division(endpoint, values):
    g.FLASK_S3UP_BUCKET_NAMESPACE = values.pop('FLASK_S3UP_BUCKET_NAMESPACE')

@blueprint.route("/files/<path:key>", methods=['GET'])
def files_download(key):
    if request.method == "GET":
        """
        key: encoded
        """
        key = urllib.parse.unquote_plus(key)
        s3_client = FlaskS3Up.get_instance(g.FLASK_S3UP_BUCKET_NAMESPACE)
        obj = s3_client.get_object(key)
        if obj:
            try:
                key = os.path.basename(key).encode('latin-1')
            except UnicodeEncodeError:
                encoded_key = unicodedata.normalize(
                    'NFKD',
                    key
                ).encode('latin-1', 'ignore')
                filenames = {
                    'filename': encoded_key,
                    'filename*': "UTF-8''{}".format(url_quote(key)),
                }
            else:
                filenames = {'filename': key}
            rv = Response(
                FileWrapper(obj.get('Body')),
                direct_passthrough=True,
                mimetype=obj['ContentType']
            )
            rv.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            rv.headers['Pragma'] = 'no-cache'
            rv.headers['Expires'] = '0'
            rv.headers.set('Content-Disposition', 'attachment', **filenames)
            return rv
        else:
            return render_template(
                f'{FLASK_S3UP_NAMESPACE}/error.html',
                message="Can't not found resource.",
                code=404
            ), 404

@blueprint.route("/files/<path:key>", methods=['DELETE'])
def files_delete(key):
    if request.method == 'DELETE':
        """
        key: decoded
        """
        s3_client = FlaskS3Up.get_instance(g.FLASK_S3UP_BUCKET_NAMESPACE)
        s3_client.delete_objects(
            key
        )
        return '', 204

@blueprint.route("/files", methods=['GET', 'POST'])
def files():
    if request.method == "POST":
        """
        prefix: encoded
        files[].f.filename: decoded
        prefixer(): 탐색 및 폴더생성시
        """
        # form
        prefix = request.form.get('prefix', '')
        prefix = urllib.parse.unquote_plus(prefix)
        files = request.files.getlist("files[]")
        s3_client = FlaskS3Up.get_instance(g.FLASK_S3UP_BUCKET_NAMESPACE)
        prefix = s3_client.prefixer(prefix)
        try:
            if not files and prefix:
                is_exists = s3_client.is_exists(prefix)
                if is_exists:
                    raise Exception('Already exists', 404)
                s3_client.put_object(prefix, mkdir=True)
                return {}, 201
            else:
                for f in files:
                    f.filename = f'{prefix}{f.filename}'
                    s3_client.upload_object(f, f.filename)
                return {}, 201
        except Exception as e:
            abort(500, str(e))

    elif request.method == "GET":
        """
        prefix: encoded
        search: decoded
        """
        # args
        prefix = request.args.get('prefix', '')
        prefix = urllib.parse.unquote_plus(prefix)
        starting_token = request.args.get('starting_token')
        search = request.args.get('search')
        page = int(request.args.get('page', 1)) - 1
        if not starting_token or starting_token == 'None':
            starting_token = None

        s3_client = FlaskS3Up.get_instance(g.FLASK_S3UP_BUCKET_NAMESPACE)
        max_items = s3_client.max_items
        max_pages = s3_client.max_pages
        if prefix:
            prefixes, contents, next_token = s3_client.list_objects(
                prefix=prefix,
                starting_token=starting_token,
                max_items=max_items*max_pages,
                search=search
            )
        else:
            prefixes, contents, next_token = s3_client.list_objects(
                starting_token=starting_token,
                max_items=max_items*max_pages,
                search=search
            )
        content_pages = [contents[i:i+max_items] for i in range(0, len(contents), max_items)]

        return render_template(
            f'{FLASK_S3UP_NAMESPACE}/files.html',
            max_pages=max_pages,
            pages=len(content_pages),
            contents=content_pages[page] if content_pages else [],
            prefixes=prefixes,
            next_token=next_token,
            object_hostname=s3_client.object_hostname
        )


@blueprint.context_processor
def utility_processor():
    def list_append(l, k):
        if k:
            if k not in l:
                l.append(k)
        return l

    def split(key, needle='/'):
        if key:
            # return map(lambda k: f'{k}', key.split(needle))
            return key.split(needle)
        return []

    def unquote_plus(key):
        return urllib.parse.unquote_plus(key)

    return dict(
        split=split,
        unquote_plus=unquote_plus,
        list_append=list_append
    )
