! ======================================================================
!  NBAL_KERNEL - the one piece of the nutrient path that is small,
!  self-contained, and worth validating on its own (MRD-231).
!
!  Agronomy's standing request (MRD-231) is to be able to say what "the
!  same answer" means before any of this model is ported off Fortran.
!  The honest obstacle has always been that the operational routines are
!  tangled up with file I/O and module state, so there is nothing clean
!  to pin a reference answer to.  This kernel is deliberately the
!  opposite: a PURE function with a fully documented scalar/array
!  interface and no I/O, no module state, no COMMON, no SAVE.  Hand it
!  the same inputs on any platform or in any language and it must return
!  the same outputs to within floating-point rounding.  It is the
!  intended first PORT TARGET.
!
!  What it computes: the day's net nitrogen mineralisation from soil
!  organic matter, per soil layer.  Each layer mineralises a temperature-
!  and moisture-limited fraction of its organic-N stock:
!
!      min(k) = RATE0 * TFAC * WFAC * ORGN(k)        kg N ha-1 day-1
!
!  TFAC is a dimensionless temperature multiplier (a Q10 response the
!  caller has already evaluated), WFAC a dimensionless moisture
!  multiplier in 0..1, RATE0 the base fractional mineralisation rate per
!  day, and ORGN(k) the organic-N stock of layer k in kg N ha-1.  The
!  outputs are the per-layer mineralisation MINOUT(k) and their sum
!  TOTAL, both kg N ha-1 day-1.
!
!  A thin NON-pure trace emitter (NMIN_TRACE) sits beside the kernel.  It
!  writes the kernel's inputs and outputs to a caller-supplied unit so a
!  recorded trace can become the reference fixture for the port.  It is
!  invoked by the nutrient driver ONLY when the MERIDIAN_TRACE switch is
!  on (see RUNOPTS); on the default run it is never called and nothing is
!  written.  It never touches MERIDIAN.OUT.
!
!  P. Nakamura, 2025-03-12.  Interface frozen for the port; see MRD-231.
! ======================================================================
module nbal_kernel
   implicit none
   private

   ! Maximum layer count the fixed-size trace record is sized for.  The
   ! nutrient path runs on the SOILWAT five-layer profile, so eight is
   ! comfortable headroom and keeps the trace format fixed-width.
   integer, parameter, public :: KN_MAXLAY = 8

   public :: nmin_kernel
   public :: nmin_trace

contains

   ! -------------------------------------------------------------------
   ! The kernel.  PURE: outputs depend only on the arguments.
   !
   !   in : nlay            number of active layers (1 .. size of arrays)
   !        orgn(nlay)      organic-N stock per layer, kg N ha-1  (>= 0)
   !        tfac            temperature multiplier, dimensionless (>= 0)
   !        wfac            moisture multiplier, dimensionless 0..1
   !        rate0           base fractional rate per day (>= 0)
   !   out: minout(nlay)    mineralised N per layer, kg N ha-1 day-1
   !        total           sum of minout over the active layers
   !
   !  Negative inputs are clamped to zero so a bad layer cannot inject
   !  nitrogen; WFAC is clamped to 0..1.  No layer may mineralise more
   !  than its own organic-N stock in a single day.
   ! -------------------------------------------------------------------
   pure subroutine nmin_kernel(nlay, orgn, tfac, wfac, rate0, minout, total)
      integer, intent(in)  :: nlay
      real,    intent(in)  :: orgn(nlay)
      real,    intent(in)  :: tfac, wfac, rate0
      real,    intent(out) :: minout(nlay)
      real,    intent(out) :: total
      integer :: k
      real    :: tf, wf, r0, stock, m

      tf = tfac
      if (tf .lt. 0.0) tf = 0.0
      wf = wfac
      if (wf .lt. 0.0) wf = 0.0
      if (wf .gt. 1.0) wf = 1.0
      r0 = rate0
      if (r0 .lt. 0.0) r0 = 0.0

      total = 0.0
      do k = 1, nlay
         stock = orgn(k)
         if (stock .lt. 0.0) stock = 0.0
         m = r0 * tf * wf * stock
         if (m .gt. stock) m = stock
         if (m .lt. 0.0) m = 0.0
         minout(k) = m
         total = total + m
      end do
   end subroutine nmin_kernel

   ! -------------------------------------------------------------------
   ! Trace emitter (NOT pure).  Writes one fixed-form record of the
   ! kernel's inputs and outputs to UNIT.  Guarded at the call site by
   ! the MERIDIAN_TRACE switch; never reached on the default run.
   !
   !   in : unit            open formatted unit to append to
   !        doy             day of year this record belongs to
   !        nlay, orgn, tfac, wfac, rate0   kernel inputs
   !        minout, total                   kernel outputs
   !
   !  The record is laid out so a port's fixture reader can parse it by
   !  column: DOY, scalar inputs, then the per-layer organic-N and
   !  per-layer mineralisation, then the total.
   ! -------------------------------------------------------------------
   subroutine nmin_trace(unit, doy, nlay, orgn, tfac, wfac, rate0, minout, total)
      integer, intent(in) :: unit, doy, nlay
      real,    intent(in) :: orgn(nlay), minout(nlay)
      real,    intent(in) :: tfac, wfac, rate0, total
      integer :: k
      write (unit, 800) doy, tfac, wfac, rate0, nlay
      write (unit, 801) (orgn(k),   k = 1, nlay)
      write (unit, 802) (minout(k), k = 1, nlay)
      write (unit, 803) total
  800 format ('NMINK DOY=', I4, ' TFAC=', F8.4, ' WFAC=', F8.4, &
              ' RATE0=', F10.6, ' NLAY=', I2)
  801 format ('  ORGN  ', 8(1X, F10.4))
  802 format ('  MINOUT', 8(1X, F10.6))
  803 format ('  TOTAL ', 1X, F12.6)
   end subroutine nmin_trace

end module nbal_kernel
