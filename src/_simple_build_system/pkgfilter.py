class PkgFilter:

    """Parse and implement the package filters defined in simplebuild.cfg data."""

    #If any positive filters are defined, a pkg must pass at least one of them to pass.
    #Furthermore, a pkg must NOT pass any of the defined negative filters, if any.
    #
    #TODO: Document filter syntax somewhere!

    def __init__( self, filter_definition_list ):
        import fnmatch
        import re
        acceptance_filters = []
        rejection_filters = []
        for forig in filter_definition_list:
            f = forig.strip()
            is_rejection = f.startswith('!')
            if is_rejection:
                f = f[1:]
            if not f:
                #Silently ignore empty entries (both "!" and "")
                continue
            if f.startswith('RE::'):
                onreldir = ''
                #print("RAW REGEX IN:",f[4:])
                regex = f[4:]
            else:
                onreldir = './' if ('/' in f) else None
                if onreldir and not f.startswith('./'):
                    f = './'+f
                regex = fnmatch.translate( f )
            try:
                reobj = re.compile(regex)
                #print("RAW REGEX PATTERN RECOGNISED:",reobj.pattern, 'FROM:',regex )
            except re.error as re:
                from . import error
                error.error(f'Invalid selection pkg filter pattern: "{forig}"')
            if is_rejection:
                rejection_filters.append( ( onreldir, reobj ) )
            else:
                acceptance_filters.append( ( onreldir, reobj ) )
        self.__accept_filters = tuple(acceptance_filters)
        self.__reject_filters = tuple(rejection_filters)

    def fully_open( self ):
        return not self.__accept_filters and not self.__reject_filters

    def dump( self ):
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
