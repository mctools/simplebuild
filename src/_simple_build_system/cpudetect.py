from . import utils

def cluster_ncpus():
    #if running at cluster via slurm, respect SLURM_CPUS_PER_TASK limit
    from os import environ as env
    cname = env.get('SLURM_CLUSTER_NAME','').strip()
    cncpu = env.get('SLURM_CPUS_PER_TASK','notfound').strip()
    if cname.lower()=='dmsc' and cncpu.isdigit():
        return int(cncpu)

def get_n_cores():
    import os
    if os.path.exists('/proc/cpuinfo'):
        #linux
        n=0
        for ll in open('/proc/cpuinfo'):
            if ( ll.startswith('processor')
                 and ll.split()[0:2]==['processor',':'] ):
                n += 1
        if not n:
            from .error import warn
            warn('Warning: Could not determine number of processors.'
                 ' Assuming just one present (override with -jN)')
            return 1
        return n
    else:
        #osx
        (ec,n)=utils.run('sysctl -n hw.ncpu')
        if ec:
            from .error import warn
            warn('Warning: Could not determine number of processors.'
                 ' Assuming just one present (override with -jN)')
            return 1
        return int(n.strip())

def get_load(ncores):
    (ec,p)=utils.run('/bin/ps -eo pcpu')
    if ec:
        from .error import warn
        warn('Warning: Could not determine current CPU load. Assuming 0%.')
        return 0.0
    if hasattr(p,'decode'):
        p=p.decode('ascii')
    p=0.01*sum([float(x.replace(',','.')) for x in p.split()[1:]])
    if p>ncores*1.5:
        from .error import warn
        warn('Warning: Could not determine current CPU load'
             ' ("ps -eo pcpu" output was suspicous). Assuming 0%.')
        return 0.0
    from os import environ as env
    if env.get('GITHUB_SERVER_URL',''): #Ignore CPU load for better performance
                                        #when using GitHub Runners (CI)
      return 0.0
    return p

def auto_njobs():
    n_reserved = cluster_ncpus()
    if n_reserved:
        return n_reserved
    nc=get_n_cores()
    freecores=nc-get_load(nc)
    return max(1,int(0.5+0.98*freecores))
