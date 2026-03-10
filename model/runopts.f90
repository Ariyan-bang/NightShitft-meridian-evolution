! ======================================================================
!  RUNOPTS - optional run switches for the Meridian cropmod.
!
!  The model has acquired a handful of OPTIONAL sub-models over the years
!  (the layered soil water in 2011, the FAO-56 ET in 2015, and now the
!  soil-nitrogen balance) that must not perturb the operational forecast.
!  The rule the agronomy group insisted on is simple: the default run,
!  with no switches set, computes and reports EXACTLY what it did before,
!  byte for byte.  A switch has to be turned on deliberately before any
!  of the newer code is allowed to execute.
!
!  Rather than extend the MERIDIAN.DAT deck (which is a fixed-width
!  contract shared with the ingest and analytics sides and may not be
!  touched), the switches are read from the environment at start-up.  An
!  unset or empty variable is OFF.  "1", "Y", "YES", "ON", "T", "TRUE"
!  (any case) are ON; anything else is OFF.  The values are read once and
!  cached so the day loop does not keep calling the C library.
!
!  P. Nakamura, 2024-11-28.  Added for the MRD-230 nutrient work; the
!  trace switch (MRD-231) rides along on the same mechanism.
! ======================================================================
module runopts
   implicit none
   private

   ! Environment variable names.  Documented here and nowhere else, so
   ! keep this list in step with any operator notes.
   character(len=*), parameter :: ENV_NBAL  = 'MERIDIAN_NBAL'
   character(len=*), parameter :: ENV_TRACE = 'MERIDIAN_TRACE'

   logical, save :: cached      = .false.
   logical, save :: nbal_flag   = .false.
   logical, save :: trace_flag  = .false.

   public :: opt_nbal
   public :: opt_trace

contains

   ! -------------------------------------------------------------------
   ! Soil-nitrogen balance switch.  OFF by default; when it returns
   ! .false. the NBALANCE path is never entered and MERIDIAN.OUT is the
   ! historical file unchanged.
   ! -------------------------------------------------------------------
   logical function opt_nbal()
      call ensure_cached()
      opt_nbal = nbal_flag
   end function opt_nbal

   ! -------------------------------------------------------------------
   ! Kernel trace switch (MRD-231).  OFF by default.  When ON, and only
   ! then, the validation kernel writes its inputs and outputs to a
   ! separate trace file; it never touches MERIDIAN.OUT.
   ! -------------------------------------------------------------------
   logical function opt_trace()
      call ensure_cached()
      opt_trace = trace_flag
   end function opt_trace

   ! -------------------------------------------------------------------
   ! Read the environment once.
   ! -------------------------------------------------------------------
   subroutine ensure_cached()
      if (cached) return
      nbal_flag  = env_is_on(ENV_NBAL)
      trace_flag = env_is_on(ENV_TRACE)
      cached     = .true.
   end subroutine ensure_cached

   ! -------------------------------------------------------------------
   ! Interpret one environment variable as a boolean.  Unset / empty /
   ! unrecognised is .false.
   ! -------------------------------------------------------------------
   logical function env_is_on(name)
      character(len=*), intent(in) :: name
      character(len=32) :: val
      integer           :: ln, status, k
      character(len=32) :: up
      character         :: c

      env_is_on = .false.
      call get_environment_variable(name, val, ln, status)
      if (status .ne. 0) return
      if (ln .le. 0) return

      ! Upper-case the (short) value in place; anything longer than the
      ! buffer cannot be one of the recognised tokens anyway.
      up = ' '
      do k = 1, min(len_trim(val), len(up))
         c = val(k:k)
         if (c .ge. 'a' .and. c .le. 'z') then
            up(k:k) = achar(iachar(c) - 32)
         else
            up(k:k) = c
         end if
      end do

      select case (trim(up))
      case ('1', 'Y', 'YES', 'ON', 'T', 'TRUE')
         env_is_on = .true.
      case default
         env_is_on = .false.
      end select
   end function env_is_on

end module runopts
