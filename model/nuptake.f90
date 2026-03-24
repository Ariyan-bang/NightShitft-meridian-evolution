! ======================================================================
!  NUPTAKE - crop nitrogen demand and uptake from the soil pools.
!
!  The growth side of the model builds dry matter each day (GROWTH, via
!  the PARTITION module).  Dry matter carries nitrogen, so each day's new
!  growth creates a nitrogen demand, and the crop meets that demand by
!  drawing mineral N out of the SOILWAT/NUTRIENT profile.  When the soil
!  cannot supply the demand the crop is N-limited, which this routine
!  reports back as a 0..1 nitrogen-stress factor that the nutrient-aware
!  season driver (NBALANCE) can fold into assimilation.
!
!  Like NUTRIENT, this is part of the OPTIONAL nitrogen balance and runs
!  only under the MERIDIAN_NBAL switch.  The default forecast never calls
!  it, so none of this affects MERIDIAN.OUT.
!
!  Demand is formed naturally in grams of N per square metre, because the
!  dry-matter increment the growth side produces is in g m-2.  The soil
!  pools, though, are areal masses in kg N ha-1 (see NUTRIENT), so the
!  demand has to be put into the pools' units before it can be drawn
!  down.  That conversion is the one unit boundary in the nitrogen path
!  and has to agree with the NUTRIENT side.
!
!  P. Nakamura, 2024-12-12.  Target N concentrations are nominal spring-
!  wheat values (critical-dilution curve), not locally fitted.
! ======================================================================
module nuptake
   use soilwat,    only : NLAYERS, ROOT_FRAC
   use nutrient,   only : npool_t, n_mineral_layer
   use phenology,  only : pheno_t, STAGE_VEG, STAGE_GRAINFIL, STAGE_MATURE
   implicit none
   private

   ! ---- areal unit conversion, g N m-2 -> kg N ha-1 ------------------
   ! A hectare is 1.0e4 m2, so one gram per square metre laid over a
   ! hectare is 1.0e4 grams per hectare; expressed in kilograms that is
   ! 100 kg ha-1.  Demand (g m-2) is multiplied by this before it is
   ! drawn from the pools (kg ha-1).
   real, parameter :: GM2_TO_KGHA = 100.0

   ! ---- target N concentration of new dry matter, g N per g DM -------
   ! Highest in vegetative tissue, diluting through grain fill as the
   ! crop lays down carbohydrate faster than it takes up nitrogen.
   real, parameter, public :: NCONC_VEG   = 0.040
   real, parameter, public :: NCONC_GRAIN = 0.021
   real, parameter, public :: NCONC_LATE  = 0.013

   ! Below this fraction of demand met, nitrogen starts to limit
   ! assimilation; at zero supply the stress factor floors at NSTR_FLOOR
   ! rather than zero (some remobilisation always occurs).
   real, parameter, public :: NSTR_FLOOR = 0.35

   public :: n_demand_gm2
   public :: n_uptake
   public :: n_stress_factor

contains

   ! -------------------------------------------------------------------
   ! Nitrogen demand of the day's new dry matter, g N m-2.
   !
   !   in : dbiom    day's dry-matter increment, g m-2 (>= 0)
   !        ph       phenology state (sets the target N concentration)
   !   out: (function) demand in g N m-2
   ! -------------------------------------------------------------------
   real function n_demand_gm2(dbiom, ph)
      real,          intent(in) :: dbiom
      type(pheno_t), intent(in) :: ph
      real :: nconc, db
      db = dbiom
      if (db .lt. 0.0) db = 0.0
      select case (ph%stage)
      case (STAGE_MATURE)
         nconc = NCONC_LATE
      case (STAGE_GRAINFIL)
         nconc = NCONC_GRAIN
      case default
         nconc = NCONC_VEG
      end select
      n_demand_gm2 = nconc * db
   end function n_demand_gm2

   ! -------------------------------------------------------------------
   ! Draw the day's nitrogen demand from the soil pools.
   !
   !   in/out: p          pools (nh4+no3 decremented by what is taken)
   !   in    : demand     demand in g N m-2 (from n_demand_gm2)
   !   out   : taken      actual uptake, kg N ha-1
   !           supplied   fraction of demand met, 0..1
   !
   !  The demand is converted to the pools' areal units and offered to
   !  each layer in proportion to rooting density times the mineral N
   !  available there, so a depleted surface throws its share onto the
   !  wetter, richer layers below - the same compensated-draw idea
   !  SOILWAT uses for water.  Ammonium and nitrate are taken in the
   !  proportion they are present in the layer.
   ! -------------------------------------------------------------------
   subroutine n_uptake(p, demand, taken, supplied)
      type(npool_t), intent(inout) :: p
      real,          intent(in)    :: demand
      real,          intent(out)   :: taken
      real,          intent(out)   :: supplied
      integer :: k
      real    :: dem_kgha, avail(NLAYERS), weight(NLAYERS)
      real    :: totw, want, take, mineral, fnh4

      ! Convert the demand (g N m-2) into the pools' areal units.
      dem_kgha = demand * GM2_TO_KGHA
      if (dem_kgha .lt. 0.0) dem_kgha = 0.0

      totw = 0.0
      do k = 1, NLAYERS
         avail(k)  = n_mineral_layer(p, k)
         weight(k) = ROOT_FRAC(k) * avail(k)
         totw      = totw + weight(k)
      end do

      taken = 0.0
      if (totw .le. 0.0) then
         supplied = 0.0
         return
      end if

      do k = 1, NLAYERS
         want = dem_kgha * (weight(k) / totw)
         take = want
         if (take .gt. avail(k)) take = avail(k)
         if (take .lt. 0.0) take = 0.0
         ! split the draw between ammonium and nitrate as present
         mineral = p%nh4(k) + p%no3(k)
         if (mineral .gt. 0.0) then
            fnh4 = p%nh4(k) / mineral
         else
            fnh4 = 0.0
         end if
         p%nh4(k) = p%nh4(k) - take * fnh4
         p%no3(k) = p%no3(k) - take * (1.0 - fnh4)
         if (p%nh4(k) .lt. 0.0) p%nh4(k) = 0.0
         if (p%no3(k) .lt. 0.0) p%no3(k) = 0.0
         taken = taken + take
      end do

      if (dem_kgha .gt. 0.0) then
         supplied = taken / dem_kgha
      else
         supplied = 1.0
      end if
      if (supplied .lt. 0.0) supplied = 0.0
      if (supplied .gt. 1.0) supplied = 1.0
   end subroutine n_uptake

   ! -------------------------------------------------------------------
   ! Nitrogen-stress factor for assimilation, 0..1, from the fraction of
   ! demand the soil met.  One when demand was fully met; declining
   ! linearly to NSTR_FLOOR as supply falls to zero.
   ! -------------------------------------------------------------------
   real function n_stress_factor(supplied)
      real, intent(in) :: supplied
      real :: s
      s = supplied
      if (s .lt. 0.0) s = 0.0
      if (s .gt. 1.0) s = 1.0
      n_stress_factor = NSTR_FLOOR + (1.0 - NSTR_FLOOR) * s
      if (n_stress_factor .lt. NSTR_FLOOR) n_stress_factor = NSTR_FLOOR
      if (n_stress_factor .gt. 1.0) n_stress_factor = 1.0
   end function n_stress_factor

end module nuptake
