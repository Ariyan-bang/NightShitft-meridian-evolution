! ======================================================================
!  NBAL - optional soil-nitrogen season balance for the Meridian cropmod.
!
!  This is the season driver for the OPTIONAL nitrogen path, the nitrogen
!  analogue of WATBAL.  It is entered ONLY when the MERIDIAN_NBAL switch
!  is set (see RUNOPTS); the default forecast never calls it, so the
!  water/growth result and MERIDIAN.OUT are untouched.  Its own output is
!  a separate diagnostic file, MERIDIAN.NUT, written fresh each run; it
!  never writes MERIDIAN.OUT.
!
!  The driver walks the season day by day and, for each day:
!
!    1. reconstructs the layered soil-water state the same way WATBAL
!       does (snow -> runoff -> infiltration cascade), because the
!       nitrogen path needs the PER-LAYER water and the PER-LAYER
!       downward flux that WATBAL only ever reported as totals;
!    2. mineralises organic N (via the shared NBAL_KERNEL, the MRD-231
!       port target; the kernel trace is emitted here when MERIDIAN_TRACE
!       is set, and only then);
!    3. nitrifies ammonium to nitrate;
!    4. forms the crop's N demand from the day's dry-matter increment
!       (BIOM, handed in from GROWTH) and draws it from the pools;
!    5. leaches mobile nitrate with the day's drainage;
!    6. records the resulting N-stress factor and pool totals.
!
!  The reconstructed water state is intentionally the same scheme as
!  WATBAL, not a shortcut: the nitrogen result is only as trustworthy as
!  the water it rides on.  The per-layer downward flux is recorded by the
!  local CASCADE_FLUX helper, which applies the same KDR rule SOILWAT
!  uses but, unlike SOILWAT's SW_INFILTRATE, hands back the flux out of
!  every layer (SW_INFILTRATE only returns the deep drainage).
!
!  P. Nakamura, 2024-12-16.
! ======================================================================
module nbal
   use soilwat,     only : NLAYERS, KDR, SW_INIT, SW_TOTAL, SW_WETNESS, &
                           SW_EVAPORATE, SW_UPTAKE
   use pet,         only : PRIESTLEY_TAYLOR
   use runoff,      only : CN2_DEFAULT, PARTITION_SURFACE
   use snow,        only : RAIN_PART, SNOW_PART, POTENTIAL_MELT
   use nutrient,    only : npool_t, n_init, n_soil_temp, n_tfactor, &
                           n_mineralise, n_nitrify, n_leach, n_mineral_total
   use nuptake,     only : n_demand_gm2, n_uptake, n_stress_factor
   use nbal_kernel, only : nmin_trace
   use runopts,     only : opt_trace
   use phenology,   only : pheno_t, pheno_reset, pheno_advance
   implicit none
   private

   public :: nbalance

contains

   ! -------------------------------------------------------------------
   ! Season driver.  Arguments mirror WATBAL/GROWTH; BIOM is the daily
   ! standing dry matter from GROWTH (g m-2), used for the N demand.
   ! Everything is intent(in) except the pools the driver owns locally;
   ! nothing the caller reported is modified, so the default path cannot
   ! be perturbed even by a programming slip here.
   ! -------------------------------------------------------------------
   subroutine nbalance(n, idoy, tmax, tmin, rain, srad, xlat, &
                       awc, rdepth, sw, et, drain, biom)
      integer, intent(in) :: n
      integer, intent(in) :: idoy(n)
      real,    intent(in) :: tmax(n), tmin(n), rain(n), srad(n)
      real,    intent(in) :: xlat, awc, rdepth
      real,    intent(in) :: sw(n), et(n), drain(n), biom(n)

      ! ---- soil-water state, mm (same geometry as WATBAL) ------------
      real :: cap(NLAYERS), wat(NLAYERS)
      real :: watlay(NLAYERS)    ! resident water per layer BEFORE cascade
      real :: drainlay(NLAYERS)  ! downward flux OUT of each layer, mm

      ! ---- nitrogen state --------------------------------------------
      type(npool_t) :: pool
      real :: minout(NLAYERS)    ! per-layer mineralisation, kg N ha-1 d-1
      real :: mintot             ! whole-profile mineralisation, kg N ha-1 d-1

      ! ---- phenology (own clock, so demand sees the right stage) -----
      type(pheno_t) :: ph

      ! ---- per-day scalars -------------------------------------------
      real :: tavg, rliq, snew, swe, pmelt, xmelt, surfac
      real :: wet, roff, infil, deep, etref, etact, frac
      real :: esoil, eact, tact, swmax
      real :: tsoil, tfac, wfac
      real :: dbiom, dem, taken, suppl, nstr, leached
      real :: tt_eff
      integer :: i, k
      logical :: tracing
      integer, parameter :: NUT_UNIT = 30
      integer, parameter :: TRC_UNIT = 31

      tracing = opt_trace()

      swmax = awc * rdepth
      if (swmax .le. 0.0) swmax = 1.0

      call sw_init(awc, rdepth, 0.60, cap, wat)
      call n_init(pool)
      call pheno_reset(ph)
      swe = 0.0

      open (unit=NUT_UNIT, file='MERIDIAN.NUT', status='UNKNOWN')
      write (NUT_UNIT, 900)
      write (NUT_UNIT, 901)
      if (tracing) then
         open (unit=TRC_UNIT, file='MERIDIAN.TRC', status='UNKNOWN')
         write (TRC_UNIT, 950)
      end if

      do i = 1, n
         tavg = 0.5 * (tmax(i) + tmin(i))

         ! --- water: snow / melt -------------------------------------
         rliq  = rain_part(rain(i), tavg)
         snew  = snow_part(rain(i), tavg)
         swe   = swe + snew
         pmelt = potential_melt(tavg)
         xmelt = pmelt
         if (xmelt .gt. swe) xmelt = swe
         swe   = swe - xmelt
         if (swe .lt. 0.0) swe = 0.0
         surfac = rliq + xmelt

         ! --- water: runoff / infiltration split ---------------------
         wet = sw_wetness(cap, wat)
         call partition_surface(surfac, CN2_DEFAULT, wet, roff, infil)

         ! --- reference ET and whole-profile stress (as WATBAL) ------
         etref = priestley_taylor(tmax(i), tmin(i), srad(i))
         frac  = sw_total(wat) / swmax
         if (frac .ge. 0.5) then
            etact = etref
         else
            etact = etref * (frac / 0.5)
         end if

         ! --- record resident water, then cascade with per-layer flux-
         do k = 1, NLAYERS
            watlay(k) = wat(k)
         end do
         call cascade_flux(cap, wat, infil, drainlay, deep)

         esoil = 0.25 * etref
         if (esoil .lt. 0.0) esoil = 0.0
         call sw_evaporate(cap, wat, esoil, eact)
         call sw_uptake(cap, wat, etact, tact)

         ! --- nitrogen: temperature / moisture limiting --------------
         tsoil = n_soil_temp(tavg)
         tfac  = n_tfactor(tsoil)
         wfac  = sw_wetness(cap, wat)

         ! --- mineralise (shared kernel) + optional trace ------------
         call n_mineralise(pool, tfac, wfac, minout, mintot)
         if (tracing) then
            call nmin_trace(TRC_UNIT, idoy(i), NLAYERS, &
                            pool%orgn, tfac, wfac, 0.0008, minout, mintot)
         end if

         ! --- nitrify -------------------------------------------------
         call n_nitrify(pool, tfac)

         ! --- crop N demand and uptake -------------------------------
         call pheno_advance(ph, tmax(i), tmin(i), xlat, idoy(i), tt_eff)
         if (i .eq. 1) then
            dbiom = biom(1)
         else
            dbiom = biom(i) - biom(i-1)
         end if
         if (dbiom .lt. 0.0) dbiom = 0.0
         dem = n_demand_gm2(dbiom, ph)
         call n_uptake(pool, dem, taken, suppl)
         nstr = n_stress_factor(suppl)

         ! --- leach mobile nitrate with the day's drainage -----------
         call n_leach(pool, watlay, drainlay, leached)

         ! --- diagnostic record --------------------------------------
         write (NUT_UNIT, 902) idoy(i), mintot, taken, leached, &
                               n_mineral_total(pool), nstr
      end do

      write (NUT_UNIT, 903)
      close (NUT_UNIT)
      if (tracing) close (TRC_UNIT)

  900 format ('MERIDIAN NBAL V0.1  (optional soil-nitrogen diagnostics)')
  901 format (' DOY     MINRL    UPTAKE     LEACH   SOILMIN   NSTRESS')
  902 format (i4, 1x, f9.4, 1x, f9.4, 1x, f9.4, 1x, f9.3, 1x, f9.4)
  903 format ('END')
  950 format ('MERIDIAN NMIN KERNEL TRACE  (MRD-231 fixture capture)')

   end subroutine nbalance

   ! -------------------------------------------------------------------
   ! Infiltration/drainage cascade that ALSO records the downward flux
   ! out of each layer.  The water arithmetic is the same KDR rule as
   ! SOILWAT's SW_INFILTRATE (infiltration to the top layer, then the
   ! above-capacity excess moved down at rate KDR, with a 1.5x ceiling);
   ! the only addition is DRAINLAY(k), the flux leaving layer k this day,
   ! which the nitrogen leaching step needs and SW_INFILTRATE does not
   ! expose.  DEEP is the flux below the bottom layer, as before.
   ! -------------------------------------------------------------------
   subroutine cascade_flux(cap, wat, infil, drainlay, deep)
      real, intent(in)    :: cap(NLAYERS)
      real, intent(inout) :: wat(NLAYERS)
      real, intent(in)    :: infil
      real, intent(out)   :: drainlay(NLAYERS)
      real, intent(out)   :: deep
      integer :: k
      real    :: excess, move, add

      do k = 1, NLAYERS
         drainlay(k) = 0.0
      end do

      add = infil
      if (add .lt. 0.0) add = 0.0
      wat(1) = wat(1) + add

      deep = 0.0
      do k = 1, NLAYERS
         if (wat(k) .gt. cap(k)) then
            excess = wat(k) - cap(k)
            move   = KDR * excess
            if (wat(k) - move .gt. 1.5 * cap(k)) then
               move = wat(k) - 1.5 * cap(k)
            end if
            wat(k)      = wat(k) - move
            drainlay(k) = move
            if (k .lt. NLAYERS) then
               wat(k+1) = wat(k+1) + move
            else
               deep = deep + move
            end if
         end if
      end do
   end subroutine cascade_flux

end module nbal
