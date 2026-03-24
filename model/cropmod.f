C=======================================================================
C  MERIDIAN CROP GROWTH AND WATER BALANCE MODEL
C  Original author: R. Halvorsen, Provincial Agronomy Branch
C  Created 1994-03-11.  Last substantive edit 1998-07-22 (see GROWTH).
C
C  DO NOT MODIFY WITHOUT RE-VALIDATING AGAINST THE FIELD TRIAL SET.
C  Validation set: 1971-2001 plot data, Kettle Ridge and Auburn sites.
C
C  Reads  : MERIDIAN.DAT   (fixed width deck, see DECKFMT.txt)
C  Writes : MERIDIAN.OUT   (fixed width, see OUTFMT.txt)
C=======================================================================
      PROGRAM CROPMOD
C-----Optional run switches and the optional soil-nitrogen balance.
C     Both default OFF: OPT_NBAL is .false. unless MERIDIAN_NBAL is set
C     in the environment, so the operational forecast never enters the
C     nitrogen path and MERIDIAN.OUT is the historical file unchanged.
      USE RUNOPTS, ONLY: OPT_NBAL
      USE NBAL,    ONLY: NBALANCE
      IMPLICIT NONE

      INTEGER MAXDAY
      PARAMETER (MAXDAY = 366)

      CHARACTER*8  STNID
      INTEGER      IYEAR, NDAYS, I, IOS
      REAL         XLAT, AWC, RDEPTH

      INTEGER      IDOY(MAXDAY)
      REAL         TMAX(MAXDAY), TMIN(MAXDAY)
      REAL         RAIN(MAXDAY), SRAD(MAXDAY)

      REAL         SW(MAXDAY), ET(MAXDAY), DRAIN(MAXDAY)
      REAL         BIOM(MAXDAY), XLAI(MAXDAY)
      REAL         YIELD

      OPEN (UNIT=10, FILE='MERIDIAN.DAT', STATUS='OLD', IOSTAT=IOS)
      IF (IOS .NE. 0) THEN
         WRITE (*,*) 'CROPMOD: cannot open MERIDIAN.DAT'
         STOP 2
      END IF

      READ (10, 900, IOSTAT=IOS) STNID, IYEAR, XLAT
      IF (IOS .NE. 0) THEN
         WRITE (*,*) 'CROPMOD: bad header record'
         STOP 3
      END IF
      READ (10, 901) AWC, RDEPTH

C-----Daily weather records.  Deck is terminated by a -1 in the DOY
C     field.  Records are assumed to be in ascending DOY order; this
C     is NOT checked (see ticket MRD-118).
      NDAYS = 0
   10 CONTINUE
         IF (NDAYS .GE. MAXDAY) GO TO 20
         READ (10, 902, IOSTAT=IOS) I, TMAX(NDAYS+1), TMIN(NDAYS+1),
     &                              RAIN(NDAYS+1), SRAD(NDAYS+1)
         IF (IOS .NE. 0) GO TO 20
         IF (I .LT. 0) GO TO 20
         NDAYS = NDAYS + 1
         IDOY(NDAYS) = I
      GO TO 10
   20 CONTINUE
      CLOSE (10)

      IF (NDAYS .LE. 0) THEN
         WRITE (*,*) 'CROPMOD: no weather records'
         STOP 4
      END IF

      CALL WATBAL (NDAYS, IDOY, TMAX, TMIN, RAIN, SRAD, XLAT,
     &             AWC, RDEPTH, SW, ET, DRAIN)

      CALL GROWTH (NDAYS, IDOY, TMAX, TMIN, SRAD, SW, AWC, XLAT,
     &             BIOM, XLAI, YIELD)

      OPEN (UNIT=20, FILE='MERIDIAN.OUT', STATUS='UNKNOWN')
      WRITE (20, 910) STNID, IYEAR, NDAYS
      WRITE (20, 911)
      DO 30 I = 1, NDAYS
         WRITE (20, 912) IDOY(I), SW(I), ET(I), DRAIN(I),
     &                   BIOM(I), XLAI(I)
   30 CONTINUE
      WRITE (20, 913) YIELD
      CLOSE (20)

C-----Optional soil-nitrogen balance (MRD-230).  Runs ONLY when the
C     MERIDIAN_NBAL switch is set; MERIDIAN.OUT has already been written
C     and closed above, and NBALANCE writes only its own diagnostic
C     files (MERIDIAN.NUT, and MERIDIAN.TRC when tracing).  The default
C     forecast skips this block entirely, so its output is unchanged.
      IF (OPT_NBAL()) THEN
         CALL NBALANCE (NDAYS, IDOY, TMAX, TMIN, RAIN, SRAD, XLAT,
     &                  AWC, RDEPTH, SW, ET, DRAIN, BIOM)
      END IF

      WRITE (*,*) 'CROPMOD: ok, ', NDAYS, ' days'
      STOP

  900 FORMAT (A8, I4, F8.3)
  901 FORMAT (F8.2, F8.2)
  902 FORMAT (I3, F6.1, F6.1, F6.1, F6.2)

  910 FORMAT ('MERIDIAN CROPMOD V2.3  STN=', A8, '  YEAR=', I4,
     &        '  NDAYS=', I4)
  911 FORMAT (' DOY      SW      ET   DRAIN    BIOM     LAI')
  912 FORMAT (I4, 1X, F7.2, 1X, F7.3, 1X, F7.3, 1X, F7.1, 1X, F7.3)
  913 FORMAT ('YIELD ', F10.3)
      END
