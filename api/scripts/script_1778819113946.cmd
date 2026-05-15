File {
   Grid = "mosfet_msh.tdr"
   Plot = "des.tdr"
   Current = "des.plt"
   Output = "des.log"
}

Electrode {
   { Name="gate"   Voltage=0.0 }
   { Name="drain"  Voltage=0.0 }
   { Name="source" Voltage=0.0 }
   { Name="substrate" Voltage=0.0 }
}

Physics {
   Temperature=300
   EffectiveIntrinsicDensity( OldSlotboom )
   Mobility( DopingDependence )
   Recombination( SRH(DopingDependence) )
}

Physics(Region="oxide") {
   EffectiveIntrinsicDensity( OldSlotboom )
}

Plot {
   eDensity hDensity
   eCurrent hCurrent
   Potential SpaceCharge
   ElectricField
   eMobility hMobility
   Doping DonorConcentration AcceptorConcentration
   BandGap ConductionBand ValenceBand
   RecombinationRate
}

Math {
   Extrapolate
   RelErrControl
   Digits=5
   Notdamped=50
   Iterations=100
   Method=ParDiSo
   SubMethod=ParDiSo
}

Solve {
   Poisson
   Coupled(Iterations=100) { Poisson Electron Hole }
   Quasistationary (
      InitialStep=0.01 Increment=1.5
      MinStep=1e-5 MaxStep=0.1
      Goal { Name="drain" Voltage=0.1 }
   ) {
      Coupled(Iterations=100) { Poisson Electron Hole }
      CurrentPlot(Time=(Range=(0 1) Intervals=10))
   }
   Quasistationary (
      InitialStep=0.01 Increment=1.5
      MinStep=1e-5 MaxStep=0.1
      Goal { Name="gate" Voltage=2.0 }
   ) {
      Coupled(Iterations=100) { Poisson Electron Hole }
      CurrentPlot(Time=(Range=(0 1) Intervals=20))
   }
}