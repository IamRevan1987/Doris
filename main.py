from core.core_drivers import apply_cpu_limits      ##  SAFETY MEASURE, DO NOT REMOVE OR CHANGE THE POSITION OF THIS LINE  ##
apply_cpu_limits()                                  ##  SAFETY MEASURE, DO NOT REMOVE OR CHANGE THE POSITION OF THIS LINE  ##
#############################################################################################################################
from interface_beta import main as initiate
# from interface_gamma import main as fallback
# from brain_ops import main as boot


##  ##                                                      ##  ##  Doris Boot Sequence  ##  ##
initiate()