class PkgFilter:

    """Parse and implement the package filters defined in simplebuild.cfg data."""

    # If any positive filters are defined, a pkg must pass at least one of them to pass.
    # If any negative filters are defined, a pkg must NOT pass any of them, to pass.

    #TODO: Document filter syntax somewhere (see also cfgtemplate.txt)!

    def __init__( self, filter_definition_list ):
        import fnmatch
        import re
        # expand on commas, strip and prune empty filters, remove duplicates:
        expanded_list = []
        for e in filter_definition_list:
            expanded_list += e.split(',')
        final_list = []
        for e in expanded_list:
            e = e.strip()
            is_rejection = e.startswith('!')
            if is_rejection:
                e = e[1:]
            if not e:
                #Silently ignore empty entries (both "!" and "")
                continue
            e = ( is_rejection, e )
            if e not in final_list:
                final_list.append( e )
        final_list.sort()

        def fmt( is_rejection, e ):
            return f'!{e}' if is_rejection else e
        single_str_list = []
        acceptance_filters = []
        rejection_filters = []
        for is_rejection, f in final_list:
            forig = fmt(is_rejection,f)
            single_str_list.append( forig )
            is_abs_dir_pattern = False
            if f.startswith('RE::'):
                onreldir = ''
                regex = f[4:]
            else:
                is_abs_dir_pattern = f.startswith('/')
                if is_abs_dir_pattern:
                    from . import error
                    error.error('Absolute paths not supported in pkg filters')
                looks_like_reldir = '/' in f
                onreldir = './' if looks_like_reldir else None
                if onreldir and not f.startswith('./'):
                    f = './'+f
                regex = fnmatch.translate( f )
            try:
                reobj = re.compile(regex)
            except re.error as re:
                from . import error
                error.error(f'Invalid syntax in pkg filter pattern: "{forig}"')
            if is_rejection:
                rejection_filters.append( ( onreldir, reobj ) )
            else:
                acceptance_filters.append( ( onreldir, reobj ) )
        self.__accept_filters = tuple(acceptance_filters)
        self.__reject_filters = tuple(rejection_filters)
        self.__as_single_str = ','.join(single_str_list)

    def fully_open( self ):
        return not self.__accept_filters and not self.__reject_filters

    def dump( self ):
        from .io import print
        print( "PkgFilter::" )
        for onreldir, reobj in self.__accept_filters:
            print( f'  -> ACCEPTANCE Pattern="{reobj.pattern}", applied_to={f"{onreldir}reldir" if onreldir is not None else "pkgname"}')
        for onreldir, reobj in self.__reject_filters:
            print( f'  -> REJECTION Pattern="{reobj.pattern}", applied_to={f"{onreldir}reldir" if onreldir is not None else "pkgname"}')

    def passes( self, pkg_name, pkg_reldir ):
        if self.__accept_filters:
            accepted = False
            for onreldir, reobj in self.__accept_filters:
                p = onreldir+pkg_reldir if onreldir is not None else pkg_name
                if reobj.match( p ) is not None:
                    accepted = True
                    break
            if not accepted:
                return False
        for onreldir, reobj in self.__reject_filters:
            p = onreldir+pkg_reldir if onreldir is not None else pkg_name
            if reobj.match( p ) is not None:
                return False
        return True

    def apply( self, pkg_names_and_reldirs ):
        for name, reldir in pkg_names_and_reldirs:
            if self.passes( name, reldir ):
                yield name

    def as_string( self ):
        return self.__as_single_str

    def __str__( self ):
        return self.as_string()
