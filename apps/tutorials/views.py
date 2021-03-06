#coding=utf-8
import os
from uliweb import expose, functions, Storage
from uliweb.orm import get_model
from uliweb.utils import date

@expose('/tutorial')
class TutorialView(object):
    def __init__(self):
        self.model = get_model('tutorials')
        self.model_chapters = get_model('tutorials_chapters')
        self.model_comments = get_model('tutorials_chapters_comments')
    
    def _get_date(self, value, obj=None):
        """
        获得本地时间，加obj可以直接用到convert函数当中
        """
        from uliweb.utils.timesince import timesince

        #return date.to_local(value).strftime('%Y-%m-%d %H:%M:%S %Z')
        return timesince(value)
    
    @expose('')
    def index(self):
        """
        教程显示首页
        """
        from uliweb.utils.generic import ListView

        condition = (self.model.c.deleted==False)

        pageno = int(request.GET.get('page', 1)) - 1
        rows_per_page = int(request.GET.get('rows', 10))

#        def render(r, obj):
#            from uliweb import Storage
#            
#            data = Storage(dict(r))
#            data['image'] = obj.get_image()
#            data['author'] = unicode(obj.modified_user)
#            data['modified_date'] = self._get_date(obj.modified_date)
#            return data

        def image(value, obj):
            return obj.get_image()
    
        def author(value, obj):
            return unicode(obj.modified_user)
        
        def modified_date(value, obj):
            return self._get_date(obj.modified_date)
        
        fields_convert_map = {'image':image, 'author':author, 'modified_date':modified_date}
        
        view = ListView(self.model, condition=condition, 
            order_by=self.model.c.modified_date.desc(), pageno=pageno,
            rows_per_page=rows_per_page, fields_convert_map=fields_convert_map)
            
        view.query()
        pagination = functions.create_pagination(request.url, view.total, pageno+1, 
            rows_per_page)
        return {'pagination':pagination, 'objects':view.objects()}

#        if 'data' in request.GET:
#            def render(r, obj):
#                data = dict(r)
#                data['image'] = obj.get_image()
#                data['author'] = unicode(obj.modified_user)
#                data['modified_date'] = self._get_date(obj.modified_date)
#                return data
#            
#            view = ListView(self.model, condition=condition, 
#                order_by=self.model.c.modified_date.desc(), pageno=pageno,
#                rows_per_page=rows_per_page, render=render)
#            return json(view.json())
#        else:
#            total = self.model.filter(condition).count()
#            return {'total':total}

    def add(self):
        """
        添加新教程
        """
        from uliweb.utils.generic import AddView
        
        def get_url(**kwargs):
            return url_for(TutorialView.read, **kwargs)
        
        def pre_save(data):
            data['creator'] = request.user.id
            if request.user.id not in data['authors']:
                data['authors'].append(request.user.id)
            data['modified_date'] = date.now()
            data['modified_user'] = request.user.id
            
        def post_created_form(fcls, model):
            fcls.authors.html_attrs['url'] = '/users/search'
            fcls.authors.choices = [('', '')]
        
        view = AddView(self.model, ok_url=get_url, pre_save=pre_save, 
            post_created_form=post_created_form)
        return view.run()
    
    def _get_hits(self, obj, field_name='hits'):
        key = '__tutorialvisited__:%s:%s:%d' % (obj.tablename, request.remote_addr, obj.id)
        cache = functions.get_cache()
        v = cache.get(key, None)
        if not v:
            setattr(obj, field_name, getattr(obj, field_name)+1)
            obj.save()
            cache.set(key, 1, settings.get_var('PARA/TUTORIAL_USER_VISITED_TIMEOUT'))
        
    def view(self, id):
        """
        查看教程
        """
        from uliweb.utils.generic import DetailView
        
        obj = self.model.get_or_notfound(int(id))
        if obj.deleted:
            flash('教程已经被删除！')
            return redirect(url_for(TutorialView.index))
        
        view = DetailView(self.model, obj=obj)
        return view.run()
    
    def edit(self, id):
        """
        编辑教程
        """
        from uliweb.utils.generic import EditView

        def pre_save(obj, data):
            if request.user.id not in data['authors']:
                data['authors'].append(request.user.id)
            data['modified_date'] = date.now()
            data['modified_user'] = request.user.id

        def post_created_form(fcls, model, obj):
            fcls.authors.html_attrs['url'] = '/users/search'
            fcls.authors.query = obj.authors.all()
        
        obj = self.model.get_or_notfound(int(id))
        
        if not self._can_edit_tutorial(obj):
            flash("你无权修改教程", 'error')
            return redirect(url_for(TutorialView.read, id=id))
        
        view = EditView(self.model, ok_url=url_for(TutorialView.read, id=id), 
            obj=obj, pre_save=pre_save, post_created_form=post_created_form)
        return view.run()
        
    def delete(self, id):
        """
        删除教程
        """
        from uliweb.utils.generic import DeleteView
        
        class MyDelete(DeleteView):
            def delete(self, obj):
                obj.deleted = True
                obj.modified_user = request.user.id
                obj.modified_date = date.now()
                obj.save()
                
        obj = self.model.get_or_notfound(int(id))
        
        if not self._can_edit_tutorial(obj):
            flash("你无权删除教程", 'error')
            return redirect(url_for(TutorialView.read, id=id))
        
        view = MyDelete(self.model, ok_url=url_for(TutorialView.index), 
            obj=obj)
        return view.run()
        
    def _get_tutorial_chapters(self, tutorial_id):
        from uliweb.utils import date
        User = get_model('user')
        
        query = self.model_chapters.filter((self.model_chapters.c.tutorial == tutorial_id) & 
            (self.model_chapters.c.deleted==False))
        query.values('id', 'title', 'hits', 'parent', 'render', 'order', 'chars_count', 
            'comments_count', 'modified_date', 'modified_user')
        query.order_by(self.model_chapters.c.parent, self.model_chapters.c.order)
        for row in query:
            d = Storage(dict(row))
            d['modified_date'] = date.to_datetime(d.modified_date)
            d['modified_user'] = User.get(d.modified_user)
            yield d
        
    def _get_chapters(self, parent=None, parent_num='', objects=None):
        index = 1
        for row in objects:
            if row.parent == parent:
                cur_num = parent_num + str(index)
                yield cur_num, row
                index += 1
    
    def read(self, id):
        """
        阅读教程
        """
        from functools import partial
        
        obj = self.model.get_or_notfound(int(id))
        objects = list(self._get_tutorial_chapters(obj.id))
        
        #处理点击次数
        self._get_hits(obj)
        
        def f(parent=None, num='', objects=objects):
            return self._get_chapters(parent, num, objects)
        
        return {'object':obj, 'objects':f, 'get_date':self._get_date}
    
    def add_chapter(self, t_id):
        """
        増加章节, t_id为教程id
        """
        from uliweb.utils.generic import AddView
        from sqlalchemy.sql import func
        
        obj = self.model.get_or_notfound(int(t_id))

        if not self._can_edit_tutorial(obj):
            flash("你无权添加新章节", 'error')
#            return redirect(url_for(TutorialView.read, id=t_id))
            Redirect(url_for(TutorialView.read, id=t_id))
        
        def get_url(**kwargs):
            return url_for(TutorialView.view_chapter, **kwargs)
        
        def pre_save(data):
            if 'parent' in request.GET:
                data['parent'] = int(request.GET.get('parent'))
            data['tutorial'] = int(t_id)
            order, = self.model_chapters.filter(self.model_chapters.c.tutorial==int(t_id)).values_one(func.max(self.model_chapters.c.order))
            data['order'] = order+1 if order>0 else 1
#            data['content'] = self._prepare_content(data['content'], data['render'])
            data['html'] = self._get_chapter_html(data['content'], data['format'], data['render'], data['scrollable'])
            data['chars_count'] = len(data['content'])
            data['modified_date'] = date.now()
            data['modified_user'] = request.user.id
            data['format'] = '2'
            
        def post_save(obj, data):
            obj.tutorial.modified_date = date.now()
            obj.tutorial.modified_user = request.user.id
            obj.tutorial.save();
            
            #删除章节顺序cache
            cache = functions.get_cache()
            cache.delete(self._get_tutorial_chapters_cache_key(int(t_id)))
            
        template_data = {'object':obj}
        data = {'scrollable':True}
        view = AddView(self.model_chapters, ok_url=get_url, pre_save=pre_save,
            template_data=template_data, post_save=post_save, data=data)
        return view.run()
    
    def _can_edit_tutorial(self, obj):
        from uliweb import request
        
        return (obj.authors.has(request.user) or 
            functions.has_role(request.user, 'superuser'))
        
    def _get_chapter_html(self, text, format, render, scrollable):
        from par.bootstrap_ext import blocks
        from md_ext import new_code_comment
        
        if format == '1':
            from par.gwiki import WikiGrammar as grammar
            from par.gwiki import WikiHtmlVisitor as parser
            from tut_parser import WikiRevealVisitor as reveal
        elif format == '2':
            from par.md import MarkdownGrammar as grammar
            from par.md import MarkdownHtmlVisitor as parser
            from tut_parser import MDRevealVisitor as reveal
        if render == '2':
            parser = reveal
        
        g = grammar()
        result, rest = g.parse(text, resultSoFar=[], skipWS=False)
        
        if render == '2':
            t = parser(grammar=g, tag_class={'table':'table table-bordered'})
        else:
            blocks['code-comment'] = new_code_comment
            cls = 'prettyprint linenums'
            if scrollable:
                cls += ' pre-scrollable'
            t = parser(grammar=g, tag_class={'table':'table table-bordered', 
                    'pre':cls}, 
                block_callback=blocks)
            
        content = t.visit(result, root=True)
        return content
    
    def _get_tutorial_chapters_cache_key(self, tutorial_id):
        return '__tutorials__:chapters_order:%d' % tutorial_id
        
    def view_chapter(self, id):
        """
        查看教程
        """
        
        obj = self.model_chapters.get_or_notfound(int(id))
        if obj.deleted:
            flash('此章节已经被删除！')
            return redirect(url_for(TutorialView.read, id=obj._tutorial_))
        
        #处理点击次数
        self._get_hits(obj)
        
        if not obj.html:
            obj.html = self._get_chapter_html(obj.content, obj.format, obj.render, obj.scrollable)
            obj.save()
        
        if obj.render == '2': #reveal
            response.template = 'TutorialView/render_reveal.html'
            
        #处理上一章和下一章功能，思路是利用缓存，如果存在，则从缓存中取出，如果不存在
        #则创建，保存格式为一个list，这样查找时进行遍历，只保存id和名称
        
        cache = functions.get_cache()
        key = self._get_tutorial_chapters_cache_key(obj._tutorial_)
        value = cache.get(key, None)
        if not value:
            chapters = []
            objects = list(self._get_tutorial_chapters(obj._tutorial_))
            def f(parent=None, n=''):
                for num, row in self._get_chapters(parent, objects=objects):
                    chapters.append({'id':row.id, 'title':n + num + ' ' + row.title})
                    f(row.id, n+num+'.')
            
            f()
            
            value = chapters
            cache.set(key, value, settings.get_var('TUTORIALS/TUTORIAL_CHAPTERS_NAV_TIMEOUT'))
            
        prev = None
        next = None
        for i in range(len(value)):
            if value[i]['id'] == obj.id:
                if i>0:
                    prev = value[i-1]
                if i != len(value)-1:
                    next = value[i+1]
                break
            
        return {'object':obj, 'html':obj.html, 'theme':obj.get_display_value('theme'), 
            'prev':prev, 'next':next}
    
#    def _prepare_content(self, text, render='html'):
#        """
#        对文本进行预处理，对每个段落识别[[#]]标记，计算最大值，同时如果不存在，
#        则自动添加[[#]]
#        """
#        from tut_parser import TutCVisitor, TutTextVisitor
#        from par.md import MarkdownGrammar
#        
#        if render == '1':   #html
#            g = MarkdownGrammar()
#            result, rest = g.parse(text, resultSoFar=[], skipWS=False)
#            t = TutCVisitor(g)
#            new_text = t.visit(result, True)
#            result, rest = g.parse(new_text, resultSoFar=[], skipWS=False)
#            result = TutTextVisitor(t.max_id, g).visit(result, True)
#        else:
#            result = text
#        return result
        
    def edit_chapter(self, id):
        """
        编辑章节
        """
        from uliweb.utils.generic import EditView
    
        obj = self.model_chapters.get_or_notfound(int(id))
        old_title = obj.title
        
        if not self._can_edit_tutorial(obj.tutorial):
            flash("你无权添加新章节", 'error')
            return redirect(url_for(TutorialView.view_chapter, id=id))
        
        def pre_save(obj, data):
#            data['content'] = self._prepare_content(data['content'], data['render'])
            data['html'] = self._get_chapter_html(data['content'], data['format'], data['render'], data['scrollable'])
            data['chars_count'] = len(data['content'])
            data['modified_date'] = date.now()
            data['modified_user'] = request.user.id
            
        def post_save(obj, data):
            obj.tutorial.modified_date = date.now()
            obj.tutorial.modified_user = request.user.id
            obj.tutorial.save();
            
            #删除章节顺序cache
            if old_title != obj.title:
                cache = functions.get_cache()
                cache.delete(self._get_tutorial_chapters_cache_key(obj._tutorial_))
        
        view = EditView(self.model_chapters, 
            ok_url=url_for(TutorialView.view_chapter, id=id), 
            obj=obj, pre_save=pre_save, post_save=post_save)
        return view.run()
    
    def delete_chapter(self, id):
        """
        删除章节
        删除时，如果有子结点，则子结点的父结点应变成当前结点的父结点
        """
        obj = self.model_chapters.get_or_notfound(int(id))
        tutorial = obj.tutorial
        count = obj.comments_count
        parent = obj._parent_
        
        #修改所有子结点的父结点
        obj.children_chapters.update(parent=parent)
        
        #删除章节顺序cache
        cache = functions.get_cache()
        cache.delete(self._get_tutorial_chapters_cache_key(obj._tutorial_))
        
        #删除当前章节
        obj.deleted = True
        obj.modified_user = request.user.id
        obj.modified_date = date.now()
        obj.save()
        
        #删除所属教程的评论数目
        tutorial.comments_count = max(0, tutorial.comments_count-count)
        tutorial.save()
        
        #跳转回教程展示页面
        return redirect(url_for(TutorialView.read, id=tutorial.id))
    
    def view_paragraph_comments(self, cid):
        """
        view_paragraph_comments/<cid>?para=pid
        显示某个段落的评论
        """
        
        _id = int(cid)
        pid = int(request.GET.get('para', 0))
        objects = self.model_comments.filter(
            (self.model_comments.c.chapter==_id) & 
            (self.model_comments.c.anchor==pid) &
            (self.model_comments.c.deleted==False)
        )
        
        def get_objects(objects):
            for row in objects:
                yield self._get_comment_data(row)
                
        return {'objects':get_objects(objects), 'object_id':_id, 'pid':pid}
    
    def _get_comment_data(self, obj, data=None):
        from uliweb.utils.textconvert import text2html
        from uliweb.orm import NotFound
        d = {}
        try:
            obj.modified_user
        except NotFound:
            obj.modified_user = None
            obj.save()
            
        d['username'] = unicode(obj.modified_user)
        d['image_url'] = functions.get_user_image(obj.modified_user, size=20)
        d['date'] = self._get_date(obj.modified_date)
        d['content'] = text2html(obj.content)
        return d
        
    def add_paragraph_comment(self, cid):
        """
        添加某个段落的评论
        """
        from uliweb.utils.generic import AddView
        
        def post_save(obj, data):
            t = obj.chapter.tutorial
            t.last_comment_user = request.user.id
            t.last_comment_date = date.now()
            t.comments_count += 1
            t.save()
            
            obj.chapter.comments_count += 1
            obj.chapter.save()
            
        default_data = {'chapter':int(cid), 'anchor':int(request.GET.get('para'))}
        view = AddView(self.model_comments, success_data=self._get_comment_data, 
            default_data=default_data, post_save=post_save)
        return view.run(json_result=True)
    
    def get_paragraph_comments_count(self, cid):
        """
        获得某个章节每个paragraph评论的数目
        返回结果为：
        
        {id1:count1, id2:count2,...}
        """
        from uliweb.orm import do_
        from sqlalchemy.sql import select, func, and_
        
        query = select([func.count(1), self.model_comments.c.anchor], 
            and_(self.model_comments.c.chapter==int(cid),
                self.model_comments.c.deleted==False)).group_by(self.model_comments.c.anchor)
        d = {}
        for row in do_(query):
            d[row[1]] = row[0]
        return json(d)
    
    def change_titles_order(self, id):
        """
        修改教程的顺序
        id为教程id
        """
        from json import loads
        
        d = {}
        for x in loads(request.POST['data']):
            d[int(x['id'])] = {'parent':x['parent'] or None, 'order':x['order']}
        for row in self.model_chapters.filter(self.model_chapters.c.tutorial==int(id)):
            if row.id in d:
                row.parent = d[row.id]['parent']
                row.order = d[row.id]['order']
                row.save()
        
        #删除章节顺序cache
        cache = functions.get_cache()
        cache.delete(self._get_tutorial_chapters_cache_key(int(id)))
        
        return json({'success':True})
    
    def uploadimage(self, tid):
        """
        上传图片
        :param tid: 论坛id
        """
        import Image
        from uliweb.utils.image import thumbnail_image, fix_filename
        from uliweb import json_dumps
        from uliweb.form import Form, ImageField
        
        File = get_model('tutorials_albums')
        obj = self.model.get_or_notfound(int(tid))
        
        class UploadForm(Form):
            filename = ImageField()
        
        form = UploadForm()
        flag = form.validate(request.values, request.files)
        if flag:
            filename = functions.save_file(os.path.join('tutorials', str(obj.id), form.filename.data.filename), form.filename.data.file)
            #process thumbnail
            rfilename, thumbnail = thumbnail_image(functions.get_filename(filename, filesystem=True), filename, settings.get_var('TUTORIALS/IMAGE_THUMBNAIL_SIZE'))
            thumbnail_url = functions.get_href(thumbnail)
            url = functions.get_href(filename)
            f = File(filename=filename, tutorial=int(tid))
            f.save()
            return json({'success':True, 'filename':form.filename.data.filename, 'url':url, 'thumbnail_url':thumbnail_url, 'id':f.id}, content_type="text/html;charset=utf-8")
        else:
            #如果校验失败，则再次返回Form，将带有错误信息
            return json({'success':False}, content_type="text/html;charset=utf-8")

    def getimages(self, tid):
        """
        返回图片
        :param tid: tutorial id
        """
        from uliweb.utils.image import thumbnail_image, fix_filename
        
        File = get_model('tutorials_albums')

        data = {'data':[], 'success':True}
        for row in File.filter(File.c.tutorial==int(tid)):
            d = {}
            thumbnail_filename = fix_filename(row.filename, '.thumbnail')
            d['thumbnail_url'] = functions.get_href(thumbnail_filename)
            d['url'] = functions.get_href(row.filename)
            d['id'] = row.id
            data['data'].append(d)
        return json(data)
    
    def deleteimage(self, id):
        """
        删除图片
        :param id:图片id
        """
        from uliweb.utils.image import fix_filename

        File = get_model('tutorials_albums')
        obj = File.get(int(id))
        if obj:
            thumbnail_filename = fix_filename(obj.filename, '.thumbnail')
            functions.delete_filename(thumbnail_filename)
            functions.delete_filename(obj.filename)
            obj.delete()
            return json({'success':True, 'message':'删除成功'})
        else:
            return json({'success':False, 'message':'图片没找到'})
        
    def postimage(self, tid):
        """
        处理HTML5文件上传
        :param tid:教程id
        """
        import base64
        from StringIO import StringIO
        from uliweb.utils.image import thumbnail_image, fix_filename
    
        File = get_model('tutorials_albums')
        
        if request.method == 'POST':
            _filename = os.path.join('tutorial/%s' % tid, request.values.get('filename'))
            fobj = StringIO(base64.b64decode(request.params.get('data')))
            filename = functions.save_file(_filename, fobj)
            #process thumbnail
            rfilename, thumbnail = thumbnail_image(functions.get_filename(filename, filesystem=True), filename, settings.get_var('TUTORIALS/IMAGE_THUMBNAIL_SIZE'))
            thumbnail_url = functions.get_href(thumbnail)
            url = functions.get_href(filename)
            f = File(filename=filename, tutorial=int(tid))
            f.save()
            return json({'success':True, 'data':{'filename':request.values.get('filename'), 'url':url, 'thumbnail_url':thumbnail_url, 'id':f.id}})
    