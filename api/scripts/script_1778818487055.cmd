File {
   Grid = "nmos_msh.tdr"
   Plot = "des.tdr"
   Current = "des.plt"
   Output = "des.log"
}

Electrode {
   { Name="source"   Voltage=0.0 }
   { Name="drain"    Voltage=0.0 }
   { Name="gate"     Voltage=0.0 }
   { Name="substrate" Voltage=0.0 }
}

Physics {
   AreaFactor=1e-4
   Mobility( DopingDependence HighFieldSaturation Enormal )
   EffectiveIntrinsicDensity( OldSlotboom )
   Recombination( SRH(DopingDependence) Auger )
}

Plot {
   eDensity hDensity
   eCurrent hCurrent
   Potential SpaceCharge
   ElectricField
   eMobility hMobility
   Doping DonorConcentration AcceptorConcentration
   eQuasiFermi hQuasiFermi
}

Math {
   Extrapolate
   RelErrControl
   Digits=5
   Notdamped=50
   Iterations=20
   Method=ParDiSo
   NumberOfThreads=4
}

Solve {
   Coupled(Iterations=100) { Poisson }
   Coupled(Iterations=100) { Poisson Electron Hole }
   Quasistationary ( InitialStep=0.01 MaxStep=0.1 MinStep=1e-10
                     Goal { Name="drain" Voltage=0.1 } )
   { Coupled(Iterations=100) { Poisson Electron Hole } }
   Quasistationary ( InitialStep=0.01 MaxStep=0.1 MinStep=1e-10
                     Goal { Name="gate" Voltage=1.0 } )
   { Coupled(Iterations=100) { Poisson Electron Hole } }
   Quasistationary ( InitialStep=0.01 MaxStep=0.1 MinStep=1e-10
                     Goal { Name="drain" Voltage=1.0 } )
   { Coupled(Iterations=100) { Poisson Electron Hole } }
}