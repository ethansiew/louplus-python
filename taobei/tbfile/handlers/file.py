from os import path

from flask import Blueprint, request, current_app
from werkzeug.wsgi import wrap_file
from werkzeug.exceptions import NotFound
from gridfs import GridFS
from gridfs.errors import NoFile
from flask_pymongo import BSONObjectIdConverter

from tblib.mongo import mongo
from tblib.handler import json_response, ResponseCode

from ..models import FileSchema

file = Blueprint('file', __name__, url_prefix='')


@file.route('/files', methods=['POST'])
def create_file():
    """保存表单上传文件到 GridFS
    """

    if 'file' not in request.files or request.files['file'].filename == '':
        raise NotFound()

    id = mongo.save_file(request.files['file'].filename, request.files["file"])

    _, ext = path.splitext(request.files['file'].filename)

    return json_response(id='{}{}'.format(id, ext))


@file.route('/files/<id>', methods=['GET'])
def file_info(id):
    """获取文件信息
    """

    id, _ = path.splitext(id)
    id = BSONObjectIdConverter({}).to_python(id)

    try:
        file = GridFS(mongo.db).get(id)
    except NoFile:
        raise NotFound()

    return json_response(file=FileSchema().dump(file))


def file_response(id, download=False):
    # 获取 GridFS 文件对
    try:
        file = GridFS(mongo.db).get(id)
    except NoFile:
        raise NotFound()

    # 将 GridFS 文件对象包装为一个 WSGI 文件对象
    data = wrap_file(request.environ, file, buffer_size=1024 * 255)
    # 创建一个 Flask Response 对象来响应文件内容
    response = current_app.response_class(
        data,
        mimetype=file.content_type,
        direct_passthrough=True,
    )
    # 设置内容长度响应头
    response.content_length = file.length
    # 设置内容最后修改时间 和 Etag 响应头，浏览器可根据这些信息来判断文件内容是否有更新
    response.last_modified = file.upload_date
    response.set_etag(file.md5)
    # 设置缓存时间和公开性响应头，这里缓存时间设为了大约一年
    response.cache_control.max_age = 365 * 24 * 3600
    response.cache_control.public = True
    # 让响应变为条件性地，如果跟 request 里的头信息对比发现浏览器里已经缓存有最新内容，那么本次响应内容将为空
    response.make_conditional(request)
    # 如果是下载模式，需要添加 Content-Disposition 响应头
    # 注意 filename 需要编码为 utf-8，否则中文会乱码
    if download:
        response.headers.set(
            'Content-Disposition', 'attachment', filename=file.filename.encode('utf-8'))

    return response


@file.route('/<id>', methods=['GET'])
def view_file(id):
    """浏览文件内容，在浏览器里直接展示文件内容，比如图片
    """

    id, _ = path.splitext(id)
    id = BSONObjectIdConverter({}).to_python(id)

    return file_response(id)


@file.route('/<id>/download', methods=['GET'])
def download_file(id):
    """下载文件内容，让浏览器打开一个保存窗口来保存文件
    """

    id, _ = path.splitext(id)
    id = BSONObjectIdConverter({}).to_python(id)

    return file_response(id, True)
