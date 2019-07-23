def get_keys(iter_, prefix=[]):
    """Return all different incremental paths
    within the the given iterable.

    A path is given as the sequence of keys obtained
    from dictionaries within the iterable given.
    """
    if type(iter_) == list:
        out = set()
        for element in iter_:
            keys = get_keys(element, prefix)
            out.update(tuple([key for key in keys]))
        return out
    elif type(iter_) == dict:
        keys = list(iter_.keys())
        out = set()
        for key in keys:
            out.add(tuple(prefix + [key]))
            child = iter_[key]
            if type(child) == dict or type(child) == list:
                out.update(get_keys(child, prefix + [key]))
        return out
    return set()

def get_keys_filt(iter_, path = None, prefix=[]):
    """
    Perform the same operation as get_keys, but follow
    only keys from the given path.
    """
    if type(iter_) == list:
        out = set()
        for element in iter_:
            keys = get_keys_filt(element, path, prefix)
            out.update(tuple([key for key in keys]))
        return out
    elif type(iter_) == dict:
        keys = list(iter_.keys())
        if path is not None:
            keys = [key for key in iter_.keys() if key in path]
        out = set()
        for key in keys:
            out.add(tuple(prefix + [key]))
            child = iter_[key]
            if type(child) == dict or type(child) == list:
                out.update(get_keys_filt(child, path, refix + [key]))
        return out
    return set()

def query(iter_, path):
    if type(iter_) == list:
        out = []
        for element in iter_:
            r = query(element, path)
            if r is not None:
                out.append(r)
        return out
    elif type(iter_) == dict:
        try:
            search_branch = iter_[path[0]]
        except (KeyError, IndexError):
            return None # prune search branch
        if len(path) > 1:
            return query(search_branch, path[1:])
        else:
            return search_branch

def get_pointer_to(iter_, path, backpointers=[]):
    """Return the structure(s) holding the last key
    from the given path."""
    if type(iter_) == list:
        out = []
        for element in iter_:
            r = get_pointer_to(element, path, backpointers)
            if r is not None and r not in out:
                out.extend(r)
        return out
    elif type(iter_) == dict:
        try:
            search_branch = iter_[path[0]]
        except (KeyError, IndexError):
            return None # prune search branch
        if len(path) > 1:
            return get_pointer_to(search_branch, path[1:], iter_)
        else:
            return [iter_]

def get_paths_for_field(iter_, field):
    """Return all paths from the root field
    to the given field within the iterable given.
    """
    # get all keys from the iterable, if any
    paths = get_keys(iter_)
    paths = [path for path in paths if path[-1] == field]
    return paths


# ------------------------------------------------------------------------------
# API
# ------------------------------------------------------------------------------
def select(iter_, field=None):
    """Given a field name, return all values associated
    to any field named as such.
    """
    # if no field defined, return the iterable
    if field is None:
        return iter_
    # find a path (for now just one) that ends with the given field
    paths = get_paths_for_field(iter_, field)
    if len(paths) > 0:
        path  = paths[0]
        return query(iter_, path)
    else:
        return ()

def group_by(iter_, field):
    # find the field right before the given one
    paths = get_paths_for_field(iter_, field)
    path  = paths[0]
    try:
        search_field = path[-2]
    except IndexError:
        search_field = path[-1]
    groups = select(iter_, search_field)
    return {group[field] : group for group in groups}

def delete(iter_, field, value):
    """Remove (in place) elements from the collection where
    the field matches the value given.

    The entire collection and all associated data
    on the same level of the given field are removed.

    Params:
    -------
    value: either a single value or a collection of values
    """
    if type(value) in (str, int, float):
        del_values = [value]
    else:
        del_values = list(value)
    # pick the outer level where the field lies
    paths = get_paths_for_field(iter_, field)
    path  = paths[0]
    # the goal here is pick a reference to the structure(s)
    # holding the element containing the field on which
    # our deletion is based on
    back_path    = path[0:-1]
    back_field   = back_path[-1]
    backing_data = get_pointer_to(iter_, back_path)
    for back in backing_data:
        if type(back[back_field]) == dict:
            # if match the the value then remove it
            if back[back_field][field] in del_values:
                back[back_field].pop(field)
        elif type(back[back_field]) == list:
            # replace the list with a new one
            # dropping matching elements
            back[back_field] = [element for element in back[back_field]\
                    if element[field] not in del_values]

