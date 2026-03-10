! ======================================================================
!  STRESS - frost and heat stress indices for the nutrient path.
!
!  The soil-nitrogen work (NBALANCE / NUTRIENT) needs a cheap measure of
!  how badly a day's temperature extremes hurt the crop, separate from
!  the broken-line development response already in PHENOLOGY.  Two things
!  matter that thermal time alone does not capture:
!
!    * a hard overnight frost around anthesis sterilises florets and
!      knocks back the nitrogen the crop can profitably take up, and
!    * a run of very hot afternoons accelerates senescence and shuts
!      stomata, which curtails both transpiration-driven mass flow of
!      nitrate and the crop's willingness to invest in more leaf.
!
!  Neither feeds the operational water/growth path; these indices exist
!  only for the OPTIONAL nutrient balance, which is off by default.  They
!  are kept here, self-contained, so the nutrient code can read a single
!  0..1 "how good was today for the crop" factor without re-deriving the
!  temperature logic.
!
!  The indices are dimensionless, 1.0 = no stress, 0.0 = complete stress.
!  Thresholds are nominal agronomic values for spring wheat in this
!  region; there is no local frost-damage dataset to fit them against, so
!  they are deliberately gentle and documented rather than calibrated.
!
!  P. Nakamura, 2024-12-03.
! ======================================================================
module stress
   use crop_params, only : TOPT, TMAXDEV
   implicit none
   private

   ! ---- frost (cold-night) thresholds, degC ---------------------------
   ! At or above TFROST_NONE the night is warm enough that frost does no
   ! harm; at or below TFROST_KILL the damage is total.  Linear between.
   real, parameter, public :: TFROST_NONE = 0.0
   real, parameter, public :: TFROST_KILL = -8.0

   ! ---- heat (hot-afternoon) thresholds, degC -------------------------
   ! Heat stress begins at THEAT_ONSET and reaches full severity at
   ! THEAT_MAX.  THEAT_ONSET sits a little above the development optimum
   ! TOPT, THEAT_MAX a little above the development ceiling TMAXDEV, so
   ! the heat-stress index and the development cut-off tell a consistent
   ! story without being the same curve.
   real, parameter, public :: THEAT_ONSET = TOPT  + 2.0
   real, parameter, public :: THEAT_MAX   = TMAXDEV + 4.0

   ! Weight on frost vs heat when the two are combined into a single
   ! factor.  Frost is the sharper risk at this latitude, so it carries
   ! slightly more weight; the two weights sum to one.
   real, parameter, public :: W_FROST = 0.55
   real, parameter, public :: W_HEAT  = 0.45

   public :: frost_index
   public :: heat_index
   public :: thermal_stress
   public :: stress_window

contains

   ! -------------------------------------------------------------------
   ! Frost index from the day's minimum temperature, 0..1.
   !   1.0 at/above TFROST_NONE, 0.0 at/below TFROST_KILL, linear between.
   ! -------------------------------------------------------------------
   real function frost_index(tmin)
      real, intent(in) :: tmin
      if (tmin .ge. TFROST_NONE) then
         frost_index = 1.0
      else if (tmin .le. TFROST_KILL) then
         frost_index = 0.0
      else
         frost_index = (tmin - TFROST_KILL) / (TFROST_NONE - TFROST_KILL)
      end if
      if (frost_index .lt. 0.0) frost_index = 0.0
      if (frost_index .gt. 1.0) frost_index = 1.0
   end function frost_index

   ! -------------------------------------------------------------------
   ! Heat index from the day's maximum temperature, 0..1.
   !   1.0 at/below THEAT_ONSET, 0.0 at/above THEAT_MAX, linear between.
   ! -------------------------------------------------------------------
   real function heat_index(tmax)
      real, intent(in) :: tmax
      if (tmax .le. THEAT_ONSET) then
         heat_index = 1.0
      else if (tmax .ge. THEAT_MAX) then
         heat_index = 0.0
      else
         heat_index = (THEAT_MAX - tmax) / (THEAT_MAX - THEAT_ONSET)
      end if
      if (heat_index .lt. 0.0) heat_index = 0.0
      if (heat_index .gt. 1.0) heat_index = 1.0
   end function heat_index

   ! -------------------------------------------------------------------
   ! Combined thermal-stress factor for one day, 0..1.  A weighted blend
   ! of the frost and heat indices; 1.0 means neither frost nor heat hurt
   ! the crop today.  This is the single number the nutrient path reads.
   ! -------------------------------------------------------------------
   real function thermal_stress(tmax, tmin)
      real, intent(in) :: tmax, tmin
      real :: fi, hi
      fi = frost_index(tmin)
      hi = heat_index(tmax)
      thermal_stress = W_FROST * fi + W_HEAT * hi
      if (thermal_stress .lt. 0.0) thermal_stress = 0.0
      if (thermal_stress .gt. 1.0) thermal_stress = 1.0
   end function thermal_stress

   ! -------------------------------------------------------------------
   ! Running stress over a short window.  Because a single cold night or
   ! hot afternoon lingers in its effect, the nutrient path can ask for a
   ! factor smoothed over the last few days rather than today alone.  The
   ! caller passes the most recent NW daily factors (newest last) and
   ! gets back a triangularly weighted mean that leans on the most recent
   ! day.  NW <= 0 returns 1.0 (no window => no smoothing).
   !
   !   in : nw          number of daily factors supplied
   !        fac(nw)     daily thermal-stress factors, oldest first
   !   out: (function)  weighted window factor, 0..1
   ! -------------------------------------------------------------------
   real function stress_window(nw, fac)
      integer, intent(in) :: nw
      real,    intent(in) :: fac(*)
      integer :: k
      real    :: wsum, asum, w
      if (nw .le. 0) then
         stress_window = 1.0
         return
      end if
      wsum = 0.0
      asum = 0.0
      do k = 1, nw
         ! triangular weights: oldest day weight 1, newest weight nw
         w    = real(k)
         asum = asum + w * fac(k)
         wsum = wsum + w
      end do
      if (wsum .le. 0.0) then
         stress_window = 1.0
      else
         stress_window = asum / wsum
      end if
      if (stress_window .lt. 0.0) stress_window = 0.0
      if (stress_window .gt. 1.0) stress_window = 1.0
   end function stress_window

end module stress
