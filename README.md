# zmk-component-xelbo

[XELBO](https://github.com/sekigon-gonnoc/xelbo)を使用したキーボードをZMKで動作させるモジュールです。

## 定義済みノード

xelboには下記のノードが定義済みです
 - led0, led1, led2
   - gpio-led互換で、それぞれを操作するとシリアルLEDが赤、緑、青に光ります。このノードを使用することで、XIAOのRGB LEDを操作していたモジュールをXELBOに流用できます。
 - xelbo_led
   - ws2812-spi互換で、インジケータ用のWS2812を直接操作できます。SPIM2を使用しています。
 - non_lipo_battery
   - [zmk-feature-non-lipo-battery-management](https://github.com/sekigon-gonnoc/zmk-feature-non-lipo-battery-management)モジュールを使用して、乾電池の電圧を監視します。

## 設定

| 項目                                    | 説明                                                                                   | デフォルト値 |
| --------------------------------------- | -------------------------------------------------------------------------------------- | ------------ |
| `CONFIG_XELBO_GPIO_LED_BRIGHTNESS`      | led0-2を使用してシリアルLEDを操作するときの明るさ                                      | 16           |
| `CONFIG_ZMK_NON_LIPO_MIN_MV`            | 電池の最小電圧（ミリボルト単位、0%充電に対応）                                         | 1100         |
| `CONFIG_ZMK_NON_LIPO_MAX_MV`            | 電池の最大電圧（ミリボルト単位、100%充電に対応）                                       | 1300         |
| `CONFIG_ZMK_NON_LIPO_LOW_MV`            | シャットダウンのしきい値電圧（ミリボルト単位）                                         | 1050         |
| `CONFIG_ZMK_NON_LIPO_ADV_SLEEP_TIMEOUT` | アドバタイジングモードで放置された場合にデバイスがスリープするまでの時間（ミリ秒単位） | 60000        |

## XIAO nRF52840からの置き換え

* XIAO nRF52840を使用したキーボードをXELBOに置き換える場合、ビルド時のオプションに`PINMAP_PROFILE=xiao_to_xelbo`を指定すると、overlayなどのピン設定を自動で書き換えてビルドします。

```yaml
include:
  - board: xiao_ble//zmk
    shield: xelbo_tester
    artifact-name: zmk-xelbo-tester-xiao
  - board: xelbo
    shield: xelbo_tester
    artifact-name: zmk-xelbo-tester-xelbo
    cmake-args: -DPINMAP_PROFILE=xiao_to_xelbo
```

ローカルビルドの場合、`PINMAP_PROFILE=xiao_to_xelbo`を指定してビルドするとローカルの設定ファイルが書き換わります。
