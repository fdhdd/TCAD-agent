#setdep @node|sprocess@

#if @CV@ == 0
#noexec
#endif


#define Frequency  1e6

Insert= "@pwd@/PlotSection_des.cmd"

Math {
   Extrapolate
   Derivatives
   Iterations= 30
   Notdamped= 50
   *ConstRefPot
   Number_Of_Threads= 4
   -CheckUndefinedModels
}

File {
        ACExtract= "cv_n@node@"
        output=   "cv_n@node@.log" 
     }

Device cv {

electrode {
            { name= "source" voltage= 0.0  }
            { name= "drain"  voltage= 0.0  }
            { name= "gate"   voltage= 0.0 barrier= @barrier@ }
            { name= "bulk"   voltage= 0.0  }
          }

File {
   Grid=      "@tdr@"
   Parameter= "@parameter@"
   Plot=      "@tdrdat@"
   Current=   "@plot@"
}

Physics{
   area= @W@
   EffectiveIntrinsicDensity( OldSlotboom )     
}

physics (material= "Silicon")  {

	  Recombination ( SRH(DopingDep) Auger  )
          Mobility ( PhuMob HighFieldSaturation Enormal )
        }

physics( MaterialInterface= "Oxide/Silicon" ) {
          Traps ( FixedCharge Conc= @Nint@ )
}

Physics(Region= "channel"){
      Recombination( Auger SRH(DopingDep)  ) 
      Mobility ( PhuMob HighFieldSaturation Enormal )
      eQuantumPotential
      hQuantumPotential       
}

}

System {
         cv cv(gate= g drain= d source= s bulk= b)
         Vsource_pset  vg(g 0) { dc= 0}
         Vsource_pset  vd(d 0) { dc= 0}
         Vsource_pset  vs(s 0) { dc= 0}
         Vsource_pset  vb(b 0) { dc= 0}
       }

solve {
                Poisson
	Coupled(Iterations= 100 LineSearchDamping= 1e-4){ Poisson eQuantumPotential hQuantumPotential }
  	Coupled(Iterations= 100 LineSearchDamping= 1e-4){ Poisson Hole Electron eQuantumPotential hQuantumPotential  }

quasistationary (
                    Goal {parameter= vg.dc voltage= !(puts [expr -1.0*@Vdd@]
			)!}
                    Initialstep= 0.01 Maxstep= 0.15 Minstep= 1e-8
                        )
                    {Coupled {Poisson Hole Electron contact circuit eQuantumPotential hQuantumPotential} }

NewCurrentPrefix= "CV_"         
quasistationary (
                    Goal {parameter= vg.dc voltage= !(puts [expr +1.0*@Vdd@]
			)!}
                    Initialstep= 0.01 Maxstep= 0.1 Minstep= 1e-8
                        )
        { ACCoupled (
                      StartFrequency= @<Frequency>@
                      EndFrequency= @<Frequency>@
                      NumberOfPoints= 1
                      decade
                      Node(g d s b)
                      Exclude(vg vd vs vb)
                    )
        {Poisson Hole Electron contact circuit eQuantumPotential hQuantumPotential} }	
}
