File {
   Grid = "nmos_msh.tdr"
   Current = "des.plt"
   Plot = "des.tdr"
   Output = "des.log"
}

Electrode {
   { Name="gate"   Voltage=0.0 }
   { Name="source" Voltage=0.0 }
   { Name="drain"  Voltage=0.0 }
   { Name="substrate" Voltage=0.0 }
}

Physics {
   Mobility ( DopingDep )
   EffectiveIntrinsicDensity ( OldSlotboom )
   Recombination ( SRH ( DopingDep ) )
}

Plot {
   eDensity hDensity
   eCurrent hCurrent
   Potential SpaceCharge
   ElectricField
   eMobility hMobility
   eVelocity hVelocity
   Doping DonorConcentration AcceptorConcentration
   ConductionBandEnergy ValenceBandEnergy
}

Math {
   Extrapolate
   RelErrControl
   Notdamped=100
   Iterations=20
   ExitOnFailure
}

Solve {

   Coupled (Iterations=100) { Poisson }
   Coupled (Iterations=100) { Poisson Electron }
   Coupled (Iterations=100) { Poisson Electron Hole }

   Quasistationary (
      InitialStep=0.01 MinStep=1e-5 MaxStep=0.1
      Goal { Name="gate" Voltage=2.0 }
   ) { Coupled (Iterations=100) { Poisson Electron Hole } }

   Quasistationary (
      InitialStep=0.01 MinStep=1e-5 MaxStep=0.1
      Goal { Name="drain" Voltage=1.0 }
   ) { Coupled (Iterations=100) { Poisson Electron Hole } }
}