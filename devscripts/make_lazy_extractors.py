#!/usr/bin/env python3

# Allow direct execution
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from inspect import getsource

from devscripts.utils import get_filename_args, read_file, write_file

NO_ATTR = object()
STATIC_CLASS_PROPERTIES = [
    'IE_NAME', '_ENABLED', '_VALID_URL',  # Used for URL matching
    '_WORKING', 'IE_DESC', '_NETRC_MACHINE', 'SEARCH_KEY',  # Used for --extractor-descriptions
    'age_limit',  # Used for --age-limit (evaluated)
    '_RETURN_TYPE',  # Accessed in CLI only with instance (evaluated)
]
CLASS_METHODS = [
    'ie_key', 'suitable', '_match_valid_url',  # Used for URL matching
    'working', 'get_temp_id', '_match_id',  # Accessed just before instance creation
    'description',  # Used for --extractor-descriptions
    'is_suitable',  # Used for --age-limit
    'supports_login', 'is_single_video',  # Accessed in CLI only with instance
]
IE_TEMPLATE = '''
class {name}({bases}):
    _module = {module!r}
'''
MODULE_TEMPLATE = read_file('devscripts/lazy_load_template.py')

_helper_number =0
_helper_number_of_module = 100

def main():
    os.environ['YTDLP_NO_PLUGINS'] = 'true'
    os.environ['YTDLP_NO_LAZY_EXTRACTORS'] = 'true'

    lazy_extractors_filename = get_filename_args(default_outfile='yt_dlp/extractor/lazy_extractors.py')
    helperbase = get_filename_args(default_outfile='yt_dlp/extractors_helper/helper0.py')
    if not os.path.exists('yt_dlp/extractors_helper'):
        os.makedirs('yt_dlp/extractors_helper')


    from yt_dlp.extractor.extractors import _ALL_CLASSES
    from yt_dlp.extractor.common import InfoExtractor, SearchInfoExtractor

    DummyInfoExtractor = type('InfoExtractor', (InfoExtractor,), {'IE_NAME': NO_ATTR})
    module_src = '\n'.join((
        MODULE_TEMPLATE,
        '    _module = None',
        *extra_ie_code(DummyInfoExtractor),
        '\nclass LazyLoadSearchExtractor(LazyLoadExtractor):\n    pass\n' 
    ))

    write_file(helperbase, f'{module_src}\n')
    lazy_extractors_module = '\n'.join((build_ies(_ALL_CLASSES, (InfoExtractor, SearchInfoExtractor), DummyInfoExtractor)))
    write_file(lazy_extractors_filename, f'\n{lazy_extractors_module}\n')
    


def extra_ie_code(ie, base=None):
    for var in STATIC_CLASS_PROPERTIES:
        val = getattr(ie, var)
        if val != (getattr(base, var) if base else NO_ATTR):
            yield f'    {var} = {val!r}'
    yield ''

    for name in CLASS_METHODS:
        f = getattr(ie, name)
        if not base or f.__func__ != getattr(base, name).__func__:
            yield getsource(f)


def gethelper_files(fileName):
    file = get_filename_args(default_outfile='yt_dlp/extractors_helper/'+(fileName))
    return file
def get_extractor_helper_numer():
    global _helper_number
    _helper_number +=1
    return _helper_number
def peak_next_extractor_helper_numer():
    global _helper_number
    return _helper_number+1

def get_base(ie):
    bases = ', '.join({
        'InfoExtractor': 'LazyLoadExtractor',
        'SearchInfoExtractor': 'LazyLoadSearchExtractor',
    }.get(base.__name__, base.__name__) for base in ie.__bases__)
    return bases

module_map = {"LazyLoadMetaClass": 0, "LazyLoadExtractor": 0, "LazyLoadSearchExtractor": 0,}

def write_helper_file(helper_import_name, modules, helper_self_import):
    next_peak = peak_next_extractor_helper_numer()
    global module_map
    imports_to_add = ""
    imports_from_file ={}
    for im in helper_self_import:
        import_from = module_map.get(im)
        if import_from == None:
            print("import not found for:" + im )
            #print(module_map)
        else:
            imfp = imports_from_file.get(import_from)
            if imfp == None:
                imfp = [im]
                imports_from_file[import_from] = imfp
            else:
                imfp.append(im)

    for imfp in imports_from_file:
        if imfp != next_peak:
            imports_to_add += "from helper"+ str(imfp)+ " import " + (", ".join(imports_from_file.get(imfp)))+ "\n"
            
            
    
    helper_number = get_extractor_helper_numer()
    fineName = "helper"+(str(helper_number))
    file =  gethelper_files(fineName +".py")
    write_file(file, f'{imports_to_add + modules}\n')
    return "from ..extractors_helper.helper"+(str(helper_number))+(" import ")+(", ".join(helper_import_name))



def build_ies(ies, bases, attr_base):
    global module_map
    names = []
    modules_ = "\n"
    helper_import_name = []
    helper_self_import =  set()
    for ie in sort_ies(ies, bases):
        tmp =  build_lazy_ie(ie, ie.__name__, attr_base)
        modules_ = modules_+tmp+'\n'
        module_map[ie.__name__] = peak_next_extractor_helper_numer()
        for x in get_base(ie).split(","):
            helper_self_import.add(x.strip())
        if ie in ies:
            names.append(ie.__name__)
            helper_import_name.append(ie.__name__)
        if len(helper_import_name) > _helper_number_of_module :
           yield write_helper_file(helper_import_name, modules_, helper_self_import)
           helper_import_name = []
           modules_ = "\n"
           helper_self_import.clear()
        
    yield write_helper_file(helper_import_name, modules_, helper_self_import)
    helper_import_name = []
    modules_ = "\n"
    helper_self_import.clear()
    yield f'\n_ALL_CLASSES = [{", ".join(names)}]'


def sort_ies(ies, ignored_bases):
    """find the correct sorting and add the required base classes so that subclasses can be correctly created"""
    classes, returned_classes = ies[:-1], set()
    assert ies[-1].__name__ == 'GenericIE', 'Last IE must be GenericIE'
    while classes:
        for c in classes[:]:
            bases = set(c.__bases__) - {object, *ignored_bases}
            restart = False
            for b in sorted(bases, key=lambda x: x.__name__):
                if b not in classes and b not in returned_classes:
                    assert b.__name__ != 'GenericIE', 'Cannot inherit from GenericIE'
                    classes.insert(0, b)
                    restart = True
            if restart:
                break
            if bases <= returned_classes:
                yield c
                returned_classes.add(c)
                classes.remove(c)
                break
    yield ies[-1]


def build_lazy_ie(ie, name, attr_base):
    bases = get_base(ie)

    s = IE_TEMPLATE.format(name=name, module=ie.__module__, bases=bases)
    return s + '\n'.join(extra_ie_code(ie, attr_base))


if __name__ == '__main__':
    main()
