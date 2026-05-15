;########################################################################################################
;# Generic 0.35um CMOS Flow
;########################################################################################################

;# ------------------------ Source scripts found in the general script database -------------------------

source  @pwd@/./Utils/measureOxideThickness.fps

;# ------------------------------------Source tcad calibration file--------------------------------------

AdvancedCalibration

pdbSetBoolean Mechanics StressHistory 1
pdbSet ImplantData DoseControl BeamDose

;# --------------------------------Load chosen mask file from repository---------------------------------

#- reflective boundary condition for the left boundary

pdbSet ImplantData LeftBoundary Reflect

set type      @DEV_TYPE@
set lgate     @L@
source  @pwd@/./Mask/mask.fps

;# ------------------------------------- Source initial mesh file ---------------------------------------

source  @pwd@/./Grid/adaptiveMeshSettings.fps
source  @pwd@/./Grid/initialMesh.fps

;# ----------------------------- Refinement for the particular project ----------------------------------

pdbSet Diffuse Diffuse.Regrid.Steps 5
pdbSet Diffuse  Growth.Regrid.Steps 5

;# ----------------------------- Save the results of all intermediate steps------------------------------

set     SaveAllSteps 1
set     PlotNum      0

# Execute the initialMesh and initialize

initialMesh
init resistivity= 7.7 field= Boron  wafer.orient= { 1 0 0 } flat.orient= { 0 1 1 } slice.angle= [CutLine2D 0 0 1 0]

# =======================================================================
# 1 -- SAC Oxide
# =======================================================================
 
temp_ramp name= temperatureRamp temp= 750<C>  t.final= 930<C>  	time= 20<min>   
temp_ramp name= temperatureRamp temp= 930<C>  t.final= 930<C>  	time=  9<min>    
temp_ramp name= temperatureRamp temp= 930<C>  t.final= 930<C>  	time= 56<min>    flows= {N2=10.0   O2=9} pressure= 1.0   
temp_ramp name= temperatureRamp temp= 930<C>  t.final= 750<C>  	time= 80<min>   
diffuse temp_ramp= temperatureRamp 
temp_ramp clear
gas_flow  clear 

if {$SaveAllSteps} { set PlotNum 1; struct FullD tdr= n@node@_${PlotNum}_SACOxide }

# =======================================================================
# 2a - P Well Implantations
# =======================================================================

photo mask=PWELL thickness=2500<nm>

implant Boron dose= 1.2e+13 energy= 175  tilt= 7 rot= +30 
implant Boron dose= 9.0e+12 energy= 95   tilt= 7 rot= +30 
implant Boron dose= 5.0e+12 energy= 60   tilt= 7 rot= +30 

strip resist

# =======================================================================
# 2b - N Well Implantations
# =======================================================================

photo mask=NWELL thickness=2500<nm>

implant Phosphorus dose= 5.0e+12 energy= 245 tilt= 7 rot= +30 
implant Phosphorus dose= 5.0e+12 energy= 245 tilt= 7 rot= +30 
implant Arsenic    dose= 1.5e+12 energy=  85 tilt= 7 rot= +30 

strip resist

if {$SaveAllSteps} { set PlotNum 2 ; struct FullD tdr= n@node@_${PlotNum}_WellImpl }

# =======================================================================
# 3 -- Well/Channel Anneal 
# =======================================================================

temp_ramp name= temperatureRamp temp= 710<C>  t.final= 820<C>  	time= 12.000<min>   
temp_ramp name= temperatureRamp temp= 820<C>  t.final= 820<C>  	time= 27.000<min>    
temp_ramp name= temperatureRamp temp= 820<C>  t.final= 710<C>  	time= 40.0<min>      
diffuse temp_ramp= temperatureRamp  
temp_ramp clear
gas_flow  clear 

# =======================================================================
# 4 -- Oxide strip before gate oxidation 
# =======================================================================

strip oxide 

if {$SaveAllSteps} { set PlotNum 4 ; struct FullD tdr= n@node@_${PlotNum}_WellImplAnneal }

# =======================================================================
# 5 -- Gate Oxidation 
# =======================================================================

temp_ramp name= temperatureRamp temp= 710<C>  t.final= 840<C>  	time= 22<min>   flows= {N2=7.0  O2=0.25} 
temp_ramp name= temperatureRamp temp= 840<C>  t.final= 840<C>  	time= 33<min>   flows= {O2=10.0} 
temp_ramp name= temperatureRamp temp= 840<C>  t.final= 710<C>  	time= 70<min>   flows= {N2=15.0} 
diffuse temp_ramp= temperatureRamp  
temp_ramp clear
gas_flow  clear 

#set Dox 0.0

CHECKOFF
set Dox [measureOxideThickness 0.1]
set Dox [expr 1000.0 * $Dox ]
LogFile "DOE: Dox [format "%.1f" $Dox]"
CHECKON

if {$SaveAllSteps} { set PlotNum 5 ; struct FullD tdr= n@node@_${PlotNum}_GateOx }

# =======================================================================
# 6 -- Poly deposition
# =======================================================================

deposit Poly rate= 250.0<nm/min> time= 1<min>

if {$SaveAllSteps} { set PlotNum 6 ; struct FullD tdr= n@node@_${PlotNum}_PolyDepo }

# =======================================================================
# 7 -- Nitride deposition 
# =======================================================================

deposit material= { nitride }  type= isotropic  rate= 37<nm/s>  time= 1<s>  temperature= 740.0<C>

if {$SaveAllSteps} { set PlotNum 7 ; struct FullD tdr= n@node@_${PlotNum}_Nitride }

# =======================================================================
# 8 -- Gate etch
# =======================================================================

photo mask=GATE thickness=1500<nm>

etch  material= { nitride } type= anisotropic rate= 40<nm/min>   time= 1.0<min>
etch  material= PolySilicon rate= 0.260 time= 1.0 type= directional direction= {1 0.08}

strip resist

strip nitride

if {$SaveAllSteps} { set PlotNum 8; struct FullD tdr= n@node@_${PlotNum}_GateEtch }

# =======================================================================
# 9 -- Poly oxidation 
# =======================================================================

temp_ramp name= temperatureRamp temp= 720<C>  t.final= 910<C>  	time= 25<min>     
temp_ramp name= temperatureRamp temp= 910<C>  t.final= 910<C>  	time= 9<min>       
temp_ramp name= temperatureRamp temp= 910<C>  t.final= 910<C>  	time= 11.7<min>   flows= {O2=9.0} 
temp_ramp name= temperatureRamp temp= 910<C>  t.final= 910<C>  	time= 9<min>      
temp_ramp name= temperatureRamp temp= 910<C>  t.final= 720<C>  	time= 75<min>      
diffuse temp_ramp= temperatureRamp  
temp_ramp clear
gas_flow  clear 

if {$SaveAllSteps} { set PlotNum 9 ; struct FullD tdr= n@node@_${PlotNum}_PolyOxidation }

# =======================================================================
# 10a -- N-Halo implantations
# =======================================================================

photo mask= NLDD thickness= 2500<nm>

implant Boron dose= 1e+12 energy= 32  tilt= 30 rot= 0 	  
implant Boron dose= 1e+12 energy= 32  tilt= 30 rot= 90 	  
implant Boron dose= 1e+12 energy= 32  tilt= 30 rot= 180   
implant Boron dose= 1e+12 energy= 32  tilt= 30 rot= 270   

# =======================================================================
# 10a -- N-Extension implantations
# =======================================================================

implant Arsenic dose= 1.0e15 energy= 50  	tilt= 0 rot= 0 	

strip resist

# =======================================================================
# 10b -- P-Halo implantations
# =======================================================================

photo mask= PLDD thickness= 2500<nm>
implant Phosphorus dose= 1.5e+13 energy= 32  tilt= 30 rot= 0 	
implant Phosphorus dose= 1.5e+13 energy= 32  tilt= 30 rot= 90 	
implant Phosphorus dose= 1.5e+13 energy= 32  tilt= 30 rot= 180 
implant Phosphorus dose= 1.5e+13 energy= 32  tilt= 30 rot= 270 

# =======================================================================
# 10b -- P-Extension implantations
# =======================================================================

implant BF2  dose= 4.5e14  energy= 50 tilt= 0 rot= 0 

strip resist

if {$SaveAllSteps} { set PlotNum 10 ; struct FullD tdr= n@node@_${PlotNum}_LDDImplantations }

# =======================================================================
# 11 -- extension/halo annealing
# =======================================================================

temp_ramp name= temperatureRamp temp= 620<C>  t.final= 800<C>  	time= 2.3<s>    flows= {N2=4.5 O2=0.95 } 
temp_ramp name= temperatureRamp temp= 800<C>  t.final= 840<C>  	time= 0.8<s>    flows= {N2=4.5 O2=0.95 } 
temp_ramp name= temperatureRamp temp= 840<C>  t.final= 960<C>  	time= 4.8<s>    flows= {N2=4.5 O2=0.95 } 
temp_ramp name= temperatureRamp temp= 960<C>  t.final= 960<C>  	time= 12<s>     flows= {N2=4.5 O2=0.95 } 
temp_ramp name= temperatureRamp temp= 960<C>  t.final= 620<C>  	time= 10.3<s>   flows= {N2=5.0 } 
diffuse temp_ramp= temperatureRamp  
temp_ramp clear
gas_flow  clear 

if {$SaveAllSteps} { set PlotNum 11 ; struct FullD tdr= n@node@_${PlotNum}_LDDAnneal }

# =======================================================================
# 12 -- Spacer oxide deposition 
# =======================================================================

deposit material= { oxide }  type= isotropic  rate= 145<nm/s>  time= 1<s>  temperature= 750.0<C>

if {$SaveAllSteps} { set PlotNum 12 ; struct FullD tdr= n@node@_${PlotNum}_Spacer }

# =======================================================================
# 13 -- Spacer Etch 
# =======================================================================

etch  material= { oxide } type= anisotropic rate= 225<nm/min>  time= 1.0<min>
etch material= silicon rate= 0.020 time= 1.0 type= directional direction= {0.75 0.50 }
deposit Oxide rate= 1<nm/min> time= 1<min>

if {$SaveAllSteps} { set PlotNum 13 ; struct FullD tdr= n@node@_${PlotNum}_SpacerEtch }

# =======================================================================
# 14 -- SD implantation 
# =======================================================================

photo mask= NPLUS thickness= 2500<nm>
implant Arsenic dose= 5.0e+15 energy= 55 
strip resist

photo mask= PPLUS thickness= 2500<nm>
implant BF2  dose= 5.0e+15 energy= 55 
strip resist

if {$SaveAllSteps} { set PlotNum 14 ; struct FullD tdr= n@node@_${PlotNum}_SDImplantation }

# =======================================================================
# 15 -- SD Anneal
# =======================================================================

temp_ramp name= temperatureRamp temp= 630<C>  t.final= 810<C>  	time= (810-630)/72.0<s>   flows= {N2=6.0 O2=0.6} 
temp_ramp name= temperatureRamp temp= 810<C>  t.final= 900<C>  	time= (900-810)/55.0<s>   flows= {N2=6.0 O2=0.6} 
temp_ramp name= temperatureRamp temp= 900<C>  t.final= 960<C>  	time= (960-900)/28.0<s>   flows= {N2=6.0 O2=0.6} 
temp_ramp name= temperatureRamp temp= 960<C>  t.final= 960<C>  	time= 9<s>     	          flows= {N2=6.0 O2=0.6} 
temp_ramp name= temperatureRamp temp= 960<C>  t.final= 610<C>  	time= (960-610)/30.0<s>   flows= {N2=6.0 } 
diffuse temp_ramp= temperatureRamp  
temp_ramp clear
gas_flow  clear 

if {$SaveAllSteps} { set PlotNum 15 ; struct FullD tdr= n@node@_${PlotNum}_SDAnneal }

strip nitride

etch  material= { oxide } type= isotropic rate= 3<nm/min>  time= 1.0<min>

struct FullD tdr= n@node@

#split @PolyDop@

#-- POLY DOPING

if { "@DEV_TYPE@"  == "nMOS" } {

sel z= 1e10      name= BActive      PolySilicon store
sel z= 1e10      name= PActive      PolySilicon store
sel z= @PolyDop@ name= AsActive     PolySilicon store
sel z= @PolyDop@ name= NetActive    PolySilicon store

} else {

sel z= @PolyDop@  name= BActive      PolySilicon store
sel z= 1e10       name= PActive      PolySilicon store
sel z= 1e10       name= AsActive     PolySilicon store
sel z= -@PolyDop@ name= NetActive    PolySilicon store

}

;# ------------------------------------ cutting---------------------------------------------------------

set type      @DEV_TYPE@
set lgate     @L@

source @pwd@/./Mask/mask.fps

set minx  -1.0
set maxx   0.9
set miny   [expr $sim_left - 0.1]
set maxy   [expr $sim_right + 0.1]

etch cmp coord= $minx
transform cut !mesh.align min= "$minx $miny"  max= "$maxx $maxy"

set yLp 0.0
set yRp 0.0
set Ygd 0.0
set Lgeff 0.0
set Lmet 0.0

CHECKOFF

set bbox   [region name= PolySilicon_1 bbox]

set xTp    [expr 1e4*[lindex [lindex $bbox 0] 0]]
set yLp    [expr 1e4*[lindex [lindex $bbox 0] 1]]

set xBp    [expr 1e4*[lindex [lindex $bbox 1] 0]]
set yRp    [expr 1e4*[lindex [lindex $bbox 1] 1]]

set Lgeff  [format "%.3f" [expr 2*($yRp - $yLp)]]

set BBox  [grid bbox]
set miny  [lindex [lindex $BBox 0] 1]
set maxy  [lindex [lindex $BBox 1] 1]

;# -- extracting metallurgical channel length

sel  z=  { NetActive }
set  Ygd  [interpolate x= 0.050  silicon val= 2e16]
set  Lmet [format %.3e [expr 2.0*$Ygd] ]
puts "DOE: Lmet $Lmet"

CHECKON

mater add name= mySi new.like= Silicon

pdbSet Grid SnMesh DelaunayType boxmethod 
pdbSet Grid AdaptiveField Refine.Abs.Error     1e37
pdbSet Grid AdaptiveField Refine.Rel.Error     1e10
pdbSet Grid AdaptiveField Refine.Target.Length 100.0
 
line      clear
refinebox clear

refinebox interface.materials= "Silicon"

mgoals accuracy= 1e-6<um>
grid Adaptive set.min.normal.size= 0.01 \
     set.normal.growth.ratio.2d= 2.0
     
     
refinebox name= BG \
    refine.min.edge= "0.010 0.010" refine.max.edge= "10.0 10.0" \
    min= "$minx $miny" max= "$maxx $maxy" \
    refine.fields= { NetActive } \
    abs.error= { NetActive= 5e10 } def.max.asinhdiff= 0.5 \
    adaptive 
    
##--interface box
mask name= POLY segments= "$yLp $yRp" !negative

refinebox min.normal.size= 0.0005<um> normal.growth.ratio= 1.21 \
interface.materials= {mySi Silicon PolySilicon } name= INT \
mask= POLY extrusion.min= -0.015 extrusion.max= 0.020 extend= 0.020 

##--channel box
set dy [format "%.3f" [expr ($yRp - $yLp)/20.0]]
refinebox name= CHANNEL all xrefine= 0.0025 yrefine= $dy \
mask= POLY extrusion.min= -0.020 extrusion.max= 0.040 extend= 0.020 

##--second channel box
set dy [format "%.3f" [expr ($yRp - $yLp)/20.0]]
refinebox name= CHANNEL2 all xrefine= 0.002 yrefine= $dy \
mask= POLY extrusion.min= -0.005 extrusion.max= 0.020 extend= 0.020 

;#-- drain refinement
set Lbox      0.12
set dx        0.0075
set dy        0.0075

set y1 [expr $Ygd - $Lbox/2.0]
set y2 [expr $Ygd + $Lbox/2.0]
mask name= DRAIN segments= "$y1 $y2" !negative

refinebox name= DRAIN all xrefine= $dx yrefine= $dy \
mask= DRAIN extrusion.min= -0.020 extrusion.max= 0.120 

grid remesh

CHECKOFF

set bbox   [region name= Silicon_1 bbox]
set xsitop [expr 1e4*[lindex [lindex $bbox 0] 0]]

;# -- shifting the structure so that si/ox interface @ 0.0
set shift 0.0
catch {set shift [expr 0.0 - $xsitop]}
transform translate= {$shift 0}
set xsitop 0.0

pdbSetBoolean Grid No2DMerge 1

;# -- POLYGON POINTS

set xT     [expr $xBp    - 0.020]
set xB     [expr $xsitop + 0.010]
set yL     [expr $yLp    - 0.002]
set yR     [expr $yRp    - 0.010]

point clear
point name= p1 coord= "$xT $yL"
point name= p2 coord= "$xT $yR"
point name= p3 coord= "$xB $yR"
point name= p4 coord= "$xB $yL"

polygon name= chan xy points= { p1 p2 p3 p4 }

insert Adaptive polygon= "chan" replace.materials= { "Silicon" } new.material= "mySi" new.region= "channel"

CHECKON

grid remesh

#-- PLACING CONTACTS

contact name= bulk	bottom 

set xlo -0.30
set xhi -0.20
set ylo -0.05
set yhi 1e3
contact box xlo= $xlo ylo= $ylo xhi= $xhi yhi= $yhi name= gate PolySilicon

set xlo -0.05
set xhi  0.1
set ylo [expr $maxy - 0.20]
set yhi [expr $maxy + 0.20]
contact box xlo= $xlo ylo= $ylo xhi= $xhi yhi= $yhi name= drain Silicon

struct smesh= n@node@ 

region  name= channel change.material Silicon !zero.data

#-- MESHING
grid remesh

struct tdr= n@node@

fexec rm -rf n@node@_bnd.tdr
fexec tdx -mtt -y -ren "drain=source" n@node@_fps.tdr n@node@_ref.tdr
fexec mv -f n@node@_ref.tdr n@node@_fps.tdr

exit 0

;# -------------------------------------------------------------------------------------------------------

