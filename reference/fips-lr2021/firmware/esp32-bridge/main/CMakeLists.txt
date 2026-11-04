set(LR2021_DIR "../../../../../tracker/firmware/components/lr2021_transport")

idf_component_register(
    SRCS "main.cpp"
         "${LR2021_DIR}/src/lr2021_spi.cpp"
         "${LR2021_DIR}/src/esp_idf_lr2021_radio.cpp"
    INCLUDE_DIRS "."
                 "${LR2021_DIR}/include"
                 "../../rp2040-bridge/src"
    REQUIRES driver esp_timer)
