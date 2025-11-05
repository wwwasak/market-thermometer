"""
配置模块简单测试脚本（无特殊字符，兼容Windows PowerShell）
"""

from core.config import Config, get_config


def main():
    print("\n" + "=" * 60)
    print("Stage 1: Configuration Module Test")
    print("=" * 60)
    
    # 创建配置实例
    config = Config()
    print("\n[OK] Config instance created successfully")
    
    # 测试1: 基础配置读取
    print("\n" + "-" * 60)
    print("Test 1: Basic Configuration")
    print("-" * 60)
    
    attack = config.get("regime.attack_threshold")
    defense = config.get("regime.defense_threshold")
    print(f"Attack threshold: {attack}")
    print(f"Defense threshold: {defense}")
    assert attack == 70, "Attack threshold should be 70"
    assert defense == 40, "Defense threshold should be 40"
    print("[PASS] Basic configuration test")
    
    # 测试2: Z窗口配置
    print("\n" + "-" * 60)
    print("Test 2: Z Windows Configuration")
    print("-" * 60)
    
    z_windows = config.get("z_windows")
    print(f"Base window: {z_windows['base']}")
    print(f"Fast window: {z_windows['fast']}")
    print(f"Slow window: {z_windows['slow']}")
    assert z_windows['base'] == 60
    assert z_windows['fast'] == 40
    assert z_windows['slow'] == 90
    print("[PASS] Z windows test")
    
    # 测试3: 风格权重
    print("\n" + "-" * 60)
    print("Test 3: Style Weights")
    print("-" * 60)
    
    cn_attack = config.get("style_weights.CN.Attack")
    us_balanced = config.get("style_weights.US.Balanced")
    print(f"CN Attack weights: {cn_attack} (sum={sum(cn_attack)})")
    print(f"US Balanced weights: {us_balanced} (sum={sum(us_balanced)})")
    assert sum(cn_attack) == 100, "CN Attack weights should sum to 100"
    assert sum(us_balanced) == 100, "US Balanced weights should sum to 100"
    print("[PASS] Style weights test")
    
    # 测试4: 活跃权重获取
    print("\n" + "-" * 60)
    print("Test 4: Active Weights")
    print("-" * 60)
    
    active_cn = config.get_active_weights("CN")
    active_us = config.get_active_weights("US")
    print(f"CN active weights: {active_cn}")
    print(f"US active weights: {active_us}")
    assert len(active_cn) == 6, "CN should have 6 main indicators"
    assert len(active_us) == 6, "US should have 6 main indicators"
    print("[PASS] Active weights test")
    
    # 测试5: 指标配置
    print("\n" + "-" * 60)
    print("Test 5: Indicator Configuration")
    print("-" * 60)
    
    cn_main = config.get("indicators.CN.main", [])
    us_main = config.get("indicators.US.main", [])
    print(f"CN main indicators count: {len(cn_main)}")
    print(f"US main indicators count: {len(us_main)}")
    
    # 测试获取单个指标
    vix_cfg = config.get_indicator_config("US", "VIX_LOG")
    if vix_cfg:
        print(f"VIX_LOG config: {vix_cfg['name']}, z_window={vix_cfg['z_window']}")
    assert vix_cfg is not None, "VIX_LOG config should exist"
    print("[PASS] Indicator configuration test")
    
    # 测试6: 软确认权重
    print("\n" + "-" * 60)
    print("Test 6: Soft Confirm Weights")
    print("-" * 60)
    
    cn_soft = config.get("soft_confirm_weights.CN")
    us_soft = config.get("soft_confirm_weights.US")
    print(f"CN soft weights: {cn_soft}")
    print(f"US soft weights: {us_soft}")
    assert abs(sum(cn_soft.values()) - 1.0) < 0.01, "CN soft weights should sum to 1.0"
    assert abs(sum(us_soft.values()) - 1.0) < 0.01, "US soft weights should sum to 1.0"
    print("[PASS] Soft confirm weights test")
    
    # 测试7: 配置修改
    print("\n" + "-" * 60)
    print("Test 7: Configuration Modification")
    print("-" * 60)
    
    original = config.get("regime.attack_threshold")
    config.set("regime.attack_threshold", 75)
    modified = config.get("regime.attack_threshold")
    print(f"Original: {original}")
    print(f"Modified: {modified}")
    assert modified == 75, "Modified value should be 75"
    print("[PASS] Configuration modification test")
    
    # 测试8: JSON保存和加载
    print("\n" + "-" * 60)
    print("Test 8: JSON Save & Load")
    print("-" * 60)
    
    save_success = config.save_to_json("test_config.json")
    print(f"Save to JSON: {save_success}")
    assert save_success, "Save should succeed"
    
    config2 = Config()
    load_success = config2.load_from_json("test_config.json")
    print(f"Load from JSON: {load_success}")
    assert load_success, "Load should succeed"
    
    loaded_value = config2.get("regime.attack_threshold")
    print(f"Loaded value: {loaded_value}")
    assert loaded_value == 75, "Loaded value should match saved value"
    print("[PASS] JSON save & load test")
    
    # 测试9: 全局配置单例
    print("\n" + "-" * 60)
    print("Test 9: Global Config Singleton")
    print("-" * 60)
    
    cfg1 = get_config()
    cfg2 = get_config()
    print(f"Instance 1 id: {id(cfg1)}")
    print(f"Instance 2 id: {id(cfg2)}")
    assert cfg1 is cfg2, "Should be the same instance"
    print("[PASS] Global config singleton test")
    
    # 最终总结
    print("\n" + "=" * 60)
    print("All tests passed!")
    print("Stage 1: Configuration module verified successfully.")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    try:
        main()
        print("\n[SUCCESS] Configuration module is working correctly.")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()

