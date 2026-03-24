# Meridian numerical core.
# Built with gfortran since 2011; originally f77 on the HP-UX box.
# Module files (params, weather, pet, ...) must compile before the
# fixed-form routines that USE them, so the object order matters.
#
# Dependency layers (compile top to bottom):
#   params                      - constants and cultivar type
#   weather                     - derived weather (uses params)
#   pet                         - reference ET (uses params, weather)
#   soilwat, runoff, snow       - water-side modules (Aquifer)
#   phenology                   - stages (uses params, weather)
#   canopy, partition           - growth-side modules (Canopy)
#   waterbal                    - fixed-form, USEs pet+soilwat+runoff+snow
#   growth                      - free-form, USEs phenology+canopy+partition
#
#   -- optional nitrogen path (compiled always, invoked only under the
#      MERIDIAN_NBAL switch; default run never enters it) --
#   runopts                     - environment run switches
#   stress                      - frost/heat index (uses params)
#   nbal_kernel                 - MRD-231 port-target kernel (standalone)
#   nutrient                    - soil-N pools (uses soilwat, nbal_kernel)
#   nuptake                     - crop N demand/uptake (uses soilwat,
#                                 nutrient, phenology)
#   nbal                        - N season driver (USEs the water/N stack)
#
#   cropmod                     - fixed-form driver
FC      = gfortran
FFLAGS  = -O2 -std=legacy -ffixed-line-length-72 -w
F90FLAGS= -O2 -w

OBJ = params.o weather.o pet.o soilwat.o runoff.o snow.o \
      phenology.o canopy.o partition.o waterbal.o growth.o \
      runopts.o stress.o nbal_kernel.o nutrient.o nuptake.o nbal.o \
      cropmod.o

all: cropmod

cropmod: $(OBJ)
	$(FC) -o cropmod $(OBJ)

# ---- base layers --------------------------------------------------
params.o:   params.f90
	$(FC) $(F90FLAGS) -c params.f90
weather.o:  weather.f90 params.o
	$(FC) $(F90FLAGS) -c weather.f90
pet.o:      pet.f90 params.o weather.o
	$(FC) $(F90FLAGS) -c pet.f90

# ---- water side (Aquifer) -----------------------------------------
soilwat.o:  soilwat.f90
	$(FC) $(F90FLAGS) -c soilwat.f90
runoff.o:   runoff.f90
	$(FC) $(F90FLAGS) -c runoff.f90
snow.o:     snow.f90
	$(FC) $(F90FLAGS) -c snow.f90
waterbal.o: waterbal.f pet.o soilwat.o runoff.o snow.o
	$(FC) $(FFLAGS) -c waterbal.f

# ---- growth side (Canopy) -----------------------------------------
phenology.o: phenology.f90 params.o weather.o
	$(FC) $(F90FLAGS) -c phenology.f90
canopy.o:    canopy.f90 params.o phenology.o
	$(FC) $(F90FLAGS) -c canopy.f90
partition.o: partition.f90 params.o phenology.o
	$(FC) $(F90FLAGS) -c partition.f90
growth.o:    growth.f90 params.o phenology.o canopy.o partition.o
	$(FC) $(F90FLAGS) -c growth.f90

# ---- optional nitrogen path (compiled, not on the default run) ----
runopts.o:    runopts.f90
	$(FC) $(F90FLAGS) -c runopts.f90
stress.o:     stress.f90 params.o
	$(FC) $(F90FLAGS) -c stress.f90
nbal_kernel.o: nbal_kernel.f90
	$(FC) $(F90FLAGS) -c nbal_kernel.f90
nutrient.o:   nutrient.f90 soilwat.o nbal_kernel.o
	$(FC) $(F90FLAGS) -c nutrient.f90
nuptake.o:    nuptake.f90 soilwat.o nutrient.o phenology.o
	$(FC) $(F90FLAGS) -c nuptake.f90
nbal.o:       nbal.f90 soilwat.o pet.o runoff.o snow.o nutrient.o \
              nuptake.o nbal_kernel.o runopts.o phenology.o
	$(FC) $(F90FLAGS) -c nbal.f90

# ---- driver -------------------------------------------------------
cropmod.o:  cropmod.f runopts.o nbal.o
	$(FC) $(FFLAGS) -c cropmod.f

clean:
	rm -f *.o *.mod cropmod MERIDIAN.OUT MERIDIAN.NUT MERIDIAN.TRC
