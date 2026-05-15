File {
   Grid = "nmos_msh.tdr"
   Current = "des.plt"
   Plot = "des.tdr"
   Output = "des.log"
}

Electrode {
   { Name="source"   Voltage=0.0 }
   { Name="drain"    Voltage=0.0 }
   { Name="gate"     Voltage=0.0 }
   { Name="substrate" Voltage=0.0 }
}

Physics {
   Mobility ( DopingDependence HighFieldSaturation Enormal )
   EffectiveIntrinsicDensity ( BandGapNarrowing ( OldSlotboom ) )
   Recombination ( SRH ( DopingDependence ) Auger )
}

Plot {
   eDensity hDensity
   eCurrent hCurrent
   Potential SpaceCharge
   ElectricField
   eMobility hMobility
   Doping DonorConcentration AcceptorConcentration
   BandGap BandEdges
   SRHRecombination AugerRecombination
}

Math {
   Extrapolate
   RelErrControl
   Digits=5
   Notdamped=50
   Iterations=20
   Method=ParDiSo
}

Solve {
   Coupled ( Iterations=100 ) { Poisson }
   Coupled ( Iterations=100 ) { Poisson Electron Hole }
   Quasistationary ( InitialStep=0.01 Increment=1.5 MinStep=1e-6 MaxStep=0.1 Goal { Name="drain" Voltage=1.0 } ) {
      Coupled ( Iterations=100 ) { Poisson Electron Hole }
   }
   Quasistationary ( InitialStep=0.01 Increment=1.5 MinStep=1e-6 MaxStep=0.05 Goal { Name="gate" Voltage=1.0 } ) {
      Coupled ( Iterations=100 ) { Poisson Electron Hole }
   }
   NewCurrentFile="transfer"
   Quasistationary ( InitialStep=0.01 Increment=1.5 MinStep=1e-6 MaxStep=0.02 Goal { Name="gate" Voltage=3.0 } ) {
      Coupled ( Iterations=100 ) { Poisson Electron Hole }
   }
}