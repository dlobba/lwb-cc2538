import matplotlib

RC_PARAMS = {
"lines.linewidth"   : 1.5,      # line width in points
"lines.antialiased" : True,     # render lines in antialiased (no jaggies)
"patch.linewidth"   : .5,       # edge width in points.
"patch.antialiased" : True,     # render patches in antialiased (no jaggies)
"patch.facecolor"   : "C1",
"boxplot.whiskers"  : 1.0,
"boxplot.patchartist" : True,
"boxplot.showfliers"  : True,
"boxplot.flierprops.linewidth" : .8,
"boxplot.boxprops.linewidth"   : .8,
"boxplot.whiskerprops.linewidth" : .8,
"boxplot.capprops.linewidth"     : .8,
"boxplot.medianprops.linewidth" : 1.0,
"boxplot.meanprops.linewidth"   : 1.0,
"boxplot.medianprops.color"     : "black",
"font.size"         : 11.0,
"axes.linewidth"    : 0.8,          # edge linewidth
"axes.titlesize"    : "large",      # fontsize of the axes title
"axes.titlepad"     : 6.0,          # pad between axes and title in points
"axes.labelpad"     : 6.0,          # space between label and axis
"axes.labelsize"    : "large",      # space between label and axis
"axes.grid"         : True,         # display grid or not
"xtick.major.width" : 0.8,          # major tick width in points
"xtick.minor.width" : 0.6,          # minor tick width in points
"xtick.labelsize"   : "medium",     # fontsize of the tick labels
"ytick.major.width" : 0.8,          # major tick width in points
"ytick.minor.width" : 0.6,          # minor tick width in points
"ytick.labelsize"   : "medium",     # fontsize of the tick labels
"grid.linewidth"    : 0.8,          # in points
"legend.loc"        : "best",
"legend.frameon"    : True,         # if True, draw the legend on a background patch
"legend.framealpha" : 0.9,          # legend patch transparency
"legend.fancybox"   : True,         # if True, use a rounded box for the
"legend.fontsize"   : "medium",
"image.cmap"        : "tab20"
}

def init_matplotlib():
    matplotlib.style.use(["seaborn"])
    for k,v in RC_PARAMS.items():
        matplotlib.rcParams[k] = v

if __name__ == "__main__":
    pass

