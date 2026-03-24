! ======================================================================
!  NUTRIENT - soil nitrogen pools and transformations.
!
!  This is the state side of the OPTIONAL soil-nitrogen balance (the
!  season driver is NBALANCE in nbal.f90; the crop's draw on these pools
!  is in nuptake.f90).  None of it runs unless the MERIDIAN_NBAL switch
!  is set (see RUNOPTS); the default forecast never touches it.
!
!  The profile geometry is borrowed wholesale from SOILWAT so the
!  nitrogen pools sit on exactly the same five layers as the water they
!  move with.  Each layer carries three pools, all held in kg N ha-1:
!
!     ORGN - organic nitrogen (the slow pool that mineralises)
!     NH4  - ammonium  (mineral, produced by mineralisation)
!     NO3  - nitrate   (mineral, produced by nitrification, leachable)
!
!  The daily transformations are the textbook minimum: mineralisation of
!  organic N to ammonium (temperature and moisture limited, via the
!  NBAL_KERNEL), nitrification of ammonium to nitrate (temperature
!  limited, first order), and leaching of nitrate carried out of a layer
!  by the drainage water SOILWAT already computed.
!
!  UNITS NOTE.  The pools are areal masses, kg N ha-1.  Where a rate or a
!  demand is naturally expressed per square metre (g N m-2) it must be
!  converted with NAREA before it meets a pool.  1 g m-2 = 10 kg ha-1, so
!  NAREA = 10.0.  Keep every conversion in these units; the growth side's
!  N demand (nuptake.f90) is the one place this has to line up and it has
!  historically been a trap (cf. the water-stress units in MRD-204).
!
!  P. Nakamura, 2024-12-10.  Rate constants are nominal mid-range values
!  for a temperate silt loam; there is no local incubation series to fit
!  them against, so do not read them as calibrated.
! ======================================================================
module nutrient
   use soilwat, only : NLAYERS, LAYER_FRAC, ROOT_FRAC
   implicit none
   private

   ! ---- areal unit conversion ----------------------------------------
   ! kg N ha-1 per g N m-2.  1 g m-2 spread over a hectare is 10 kg.
   ! This is THE conversion between the per-area crop quantities and the
   ! soil pools; see the units note in the header.
   real, parameter, public :: NAREA = 10.0

   ! ---- transformation rate constants --------------------------------
   ! Base fractional mineralisation rate of the organic pool per day at
   ! the reference temperature and optimum moisture.  Small: the organic
   ! pool turns over slowly.
   real, parameter, public :: KMIN0 = 0.0008

   ! Q10 and reference temperature for the mineralisation temperature
   ! response.  TFAC = Q10 ** ((Tsoil - TREF)/10).
   real, parameter, public :: Q10_MIN = 2.0
   real, parameter, public :: TREF    = 20.0

   ! First-order nitrification rate of ammonium per day at reference
   ! temperature; shares the mineralisation temperature response.
   real, parameter, public :: KNIT0 = 0.20

   ! Fraction of a layer's nitrate that is mobile (travels with water);
   ! the rest is held on exchange sites and does not leach in a day.
   real, parameter, public :: NO3_MOBILE = 0.85

   ! Initial pool sizes, kg N ha-1, as whole-profile totals; split across
   ! layers below.  Organic N is large and concentrated near the surface;
   ! starting mineral N is modest (a lightly fertilised seedbed).
   real, parameter, public :: ORGN_TOTAL0 = 3000.0
   real, parameter, public :: NH4_TOTAL0  = 12.0
   real, parameter, public :: NO3_TOTAL0  = 28.0

   ! The three pools on the SOILWAT profile.  Held as plain arrays so the
   ! fixed-form NBALANCE driver can pass them without a derived type, the
   ! same discipline SOILWAT keeps for the water state.
   type, public :: npool_t
      real :: orgn(NLAYERS) = 0.0   ! organic N,  kg N ha-1
      real :: nh4(NLAYERS)  = 0.0   ! ammonium,   kg N ha-1
      real :: no3(NLAYERS)  = 0.0   ! nitrate,    kg N ha-1
   end type npool_t

   public :: n_init
   public :: n_soil_temp
   public :: n_tfactor
   public :: n_mineralise
   public :: n_nitrify
   public :: n_leach
   public :: n_mineral_total
   public :: n_mineral_layer

contains

   ! -------------------------------------------------------------------
   ! Initialise the pools.  Organic N is distributed by the SOILWAT layer
   ! thickness fractions weighted toward the surface; mineral N follows
   ! the rooting-density fractions (that is where recent residue and
   ! fertiliser sit).  Both distributions sum to one, so the whole-profile
   ! totals are preserved exactly.
   ! -------------------------------------------------------------------
   subroutine n_init(p)
      type(npool_t), intent(out) :: p
      integer :: k
      real    :: worg(NLAYERS), sorg
      ! Surface-weighted organic distribution: thickness fraction divided
      ! by a depth index, renormalised.
      sorg = 0.0
      do k = 1, NLAYERS
         worg(k) = LAYER_FRAC(k) / real(k)
         sorg    = sorg + worg(k)
      end do
      do k = 1, NLAYERS
         p%orgn(k) = ORGN_TOTAL0 * (worg(k) / sorg)
         p%nh4(k)  = NH4_TOTAL0  * ROOT_FRAC(k)
         p%no3(k)  = NO3_TOTAL0  * ROOT_FRAC(k)
      end do
   end subroutine n_init

   ! -------------------------------------------------------------------
   ! A crude soil temperature from the day's mean air temperature.  The
   ! deck has no soil probe, so soil temperature is damped air
   ! temperature: a weighted pull toward the reference, which keeps the
   ! mineralisation response from swinging as hard as the air does.
   ! -------------------------------------------------------------------
   real function n_soil_temp(tavg)
      real, intent(in) :: tavg
      real, parameter  :: DAMP = 0.7
      n_soil_temp = DAMP * tavg + (1.0 - DAMP) * TREF
   end function n_soil_temp

   ! -------------------------------------------------------------------
   ! Temperature multiplier for the biological transformations, a Q10
   ! response about TREF.  Dimensionless, >= 0.
   ! -------------------------------------------------------------------
   real function n_tfactor(tsoil)
      real, intent(in) :: tsoil
      n_tfactor = Q10_MIN ** ((tsoil - TREF) / 10.0)
      if (n_tfactor .lt. 0.0) n_tfactor = 0.0
   end function n_tfactor

   ! -------------------------------------------------------------------
   ! Mineralise organic N to ammonium for one day.  The per-layer amounts
   ! come from the shared NBAL_KERNEL (the MRD-231 port target) so there
   ! is exactly one place that defines the mineralisation arithmetic.
   ! The mineralised N leaves ORGN and enters NH4, layer by layer.
   !
   !   in/out: p         pools (orgn decremented, nh4 incremented)
   !   in    : tfac      temperature multiplier (n_tfactor)
   !           wfac      moisture multiplier, 0..1 (from SOILWAT wetness)
   !   out   : minout    per-layer mineralised N, kg N ha-1 day-1
   !           total     whole-profile mineralised N, kg N ha-1 day-1
   ! -------------------------------------------------------------------
   subroutine n_mineralise(p, tfac, wfac, minout, total)
      use nbal_kernel, only : nmin_kernel
      type(npool_t), intent(inout) :: p
      real,          intent(in)    :: tfac, wfac
      real,          intent(out)   :: minout(NLAYERS)
      real,          intent(out)   :: total
      integer :: k
      call nmin_kernel(NLAYERS, p%orgn, tfac, wfac, KMIN0, minout, total)
      do k = 1, NLAYERS
         p%orgn(k) = p%orgn(k) - minout(k)
         if (p%orgn(k) .lt. 0.0) p%orgn(k) = 0.0
         p%nh4(k)  = p%nh4(k)  + minout(k)
      end do
   end subroutine n_mineralise

   ! -------------------------------------------------------------------
   ! Nitrify ammonium to nitrate for one day: first order in NH4 with the
   ! same temperature multiplier, capped by what is there.
   ! -------------------------------------------------------------------
   subroutine n_nitrify(p, tfac)
      type(npool_t), intent(inout) :: p
      real,          intent(in)    :: tfac
      integer :: k
      real    :: rate, conv
      rate = KNIT0 * tfac
      if (rate .lt. 0.0) rate = 0.0
      if (rate .gt. 1.0) rate = 1.0
      do k = 1, NLAYERS
         conv = rate * p%nh4(k)
         if (conv .gt. p%nh4(k)) conv = p%nh4(k)
         if (conv .lt. 0.0) conv = 0.0
         p%nh4(k) = p%nh4(k) - conv
         p%no3(k) = p%no3(k) + conv
      end do
   end subroutine n_nitrify

   ! -------------------------------------------------------------------
   ! Leach nitrate with the day's water movement.  DRAINLAY(k) is the
   ! volume of water (mm) leaving layer k downward this day, and WATLAY(k)
   ! the water (mm) resident in the layer before that movement.  The
   ! mobile fraction of each layer's nitrate is carried to the layer
   ! below in the ratio of drainage to resident water; nitrate leaving
   ! the bottom layer is lost below the root zone and returned as LOSS.
   !
   !   in/out: p            pools (no3 redistributed downward)
   !   in    : watlay       resident water per layer, mm (pre-movement)
   !           drainlay     downward water flux per layer, mm
   !   out   : loss         nitrate lost below the profile, kg N ha-1
   ! -------------------------------------------------------------------
   subroutine n_leach(p, watlay, drainlay, loss)
      type(npool_t), intent(inout) :: p
      real,          intent(in)    :: watlay(NLAYERS), drainlay(NLAYERS)
      real,          intent(out)   :: loss
      integer :: k
      real    :: frac, moved, carry

      loss  = 0.0
      carry = 0.0     ! nitrate handed down from the layer above
      do k = 1, NLAYERS
         p%no3(k) = p%no3(k) + carry
         carry    = 0.0
         if (watlay(k) .gt. 0.0 .and. drainlay(k) .gt. 0.0) then
            frac = drainlay(k) / watlay(k)
            if (frac .gt. NO3_MOBILE) frac = NO3_MOBILE
            if (frac .lt. 0.0) frac = 0.0
            moved = frac * p%no3(k)
            p%no3(k) = p%no3(k) - moved
            if (k .lt. NLAYERS) then
               carry = moved
            else
               loss = loss + moved
            end if
         end if
      end do
   end subroutine n_leach

   ! -------------------------------------------------------------------
   ! Plant-available mineral N in a layer, kg N ha-1: ammonium plus
   ! nitrate.  The crop draws on this (see nuptake.f90).
   ! -------------------------------------------------------------------
   real function n_mineral_layer(p, k)
      type(npool_t), intent(in) :: p
      integer,       intent(in) :: k
      n_mineral_layer = p%nh4(k) + p%no3(k)
      if (n_mineral_layer .lt. 0.0) n_mineral_layer = 0.0
   end function n_mineral_layer

   ! -------------------------------------------------------------------
   ! Whole-profile mineral N, kg N ha-1.
   ! -------------------------------------------------------------------
   real function n_mineral_total(p)
      type(npool_t), intent(in) :: p
      integer :: k
      n_mineral_total = 0.0
      do k = 1, NLAYERS
         n_mineral_total = n_mineral_total + p%nh4(k) + p%no3(k)
      end do
   end function n_mineral_total

end module nutrient
