"""
配置模块快速测试脚本
用于验证阶段1的配置加载功能
"""

from core.config import Config, get_config
import json


def test_basic_config():
    """测试基础配置加载"""
    print("=" * 60)
    print("测试1: 基础配置加载")
    print("=" * 60)
    
    config = Config()
    
    # 测试获取默认配置
    attack_threshold = config.get("regime.attack_threshold")
    defense_threshold = config.get("regime.defense_threshold")
    
    print(f"✓ Regime阈值加载成功:")
    print(f"  - Attack阈值: {attack_threshold}")
    print(f"  - Defense阈值: {defense_threshold}")
    
    # 测试Z窗口配置
    z_windows = config.get("z_windows")
    print(f"\n✓ Z窗口配置:")
    print(f"  - 基础窗口: {z_windows['base']}")
    print(f"  - 快速窗口: {z_windows['fast']}")
    print(f"  - 慢速窗口: {z_windows['slow']}")
    
    return True


def test_style_weights():
    """测试风格权重配置"""
    print("\n" + "=" * 60)
    print("测试2: 风格权重配置")
    print("=" * 60)
    
    config = Config()
    
    # CN市场权重
    cn_weights = config.get("style_weights.CN")
    print(f"\n✓ CN市场风格权重:")
    for style, weights in cn_weights.items():
        print(f"  {style}: {weights} (总和: {sum(weights)})")
    
    # US市场权重
    us_weights = config.get("style_weights.US")
    print(f"\n✓ US市场风格权重:")
    for style, weights in us_weights.items():
        print(f"  {style}: {weights} (总和: {sum(weights)})")
    
    # 测试活跃风格
    active_cn = config.get("active_style.CN")
    active_us = config.get("active_style.US")
    print(f"\n✓ 当前活跃风格:")
    print(f"  CN: {active_cn}")
    print(f"  US: {active_us}")
    
    # 测试获取活跃权重的便捷方法
    active_cn_weights = config.get_active_weights("CN")
    print(f"\n✓ CN当前活跃权重: {active_cn_weights}")
    
    return True


def test_indicator_config():
    """测试指标配置"""
    print("\n" + "=" * 60)
    print("测试3: 指标配置")
    print("=" * 60)
    
    config = Config()
    
    # CN市场主要指标
    cn_main = config.get("indicators.CN.main", [])
    print(f"\n✓ CN市场主要指标 ({len(cn_main)}个):")
    for ind in cn_main[:3]:  # 只显示前3个
        print(f"  - {ind['code']}: {ind['name']} ({ind['direction']})")
    print("  ...")
    
    # US市场主要指标
    us_main = config.get("indicators.US.main", [])
    print(f"\n✓ US市场主要指标 ({len(us_main)}个):")
    for ind in us_main[:3]:
        print(f"  - {ind['code']}: {ind['name']} ({ind['direction']})")
    print("  ...")
    
    # 测试获取单个指标配置
    vix_config = config.get_indicator_config("US", "VIX_LOG")
    if vix_config:
        print(f"\n✓ VIX_LOG指标配置:")
        print(f"  名称: {vix_config['name']}")
        print(f"  方向: {vix_config['direction']}")
        print(f"  转换: {vix_config['transform']}")
        print(f"  Z类型: {vix_config['z_type']}")
        print(f"  Z窗口: {vix_config['z_window']}")
    
    return True


def test_set_and_save():
    """测试配置修改和保存"""
    print("\n" + "=" * 60)
    print("测试4: 配置修改和保存")
    print("=" * 60)
    
    config = Config()
    
    # 修改配置
    original_threshold = config.get("regime.attack_threshold")
    print(f"✓ 原始Attack阈值: {original_threshold}")
    
    config.set("regime.attack_threshold", 75)
    new_threshold = config.get("regime.attack_threshold")
    print(f"✓ 修改后Attack阈值: {new_threshold}")
    
    # 保存到JSON
    success = config.save_to_json("test_config.json")
    if success:
        print(f"✓ 配置已保存到 test_config.json")
    
    # 创建新实例并加载
    config2 = Config()
    config2.load_from_json("test_config.json")
    loaded_threshold = config2.get("regime.attack_threshold")
    print(f"✓ 从文件加载的Attack阈值: {loaded_threshold}")
    
    # 验证是否一致
    assert loaded_threshold == 75, "配置加载验证失败"
    print(f"✓ 配置持久化验证通过")
    
    return True


def test_soft_confirm_weights():
    """测试软确认权重配置"""
    print("\n" + "=" * 60)
    print("测试5: 软确认权重配置")
    print("=" * 60)
    
    config = Config()
    
    # CN市场软确认权重
    cn_soft = config.get("soft_confirm_weights.CN")
    print(f"\n✓ CN市场软确认权重:")
    for key, weight in cn_soft.items():
        print(f"  {key}: {weight}")
    print(f"  总和: {sum(cn_soft.values())}")
    
    # US市场软确认权重
    us_soft = config.get("soft_confirm_weights.US")
    print(f"\n✓ US市场软确认权重:")
    for key, weight in us_soft.items():
        print(f"  {key}: {weight}")
    print(f"  总和: {sum(us_soft.values())}")
    
    return True


def test_global_config():
    """测试全局配置单例"""
    print("\n" + "=" * 60)
    print("测试6: 全局配置单例")
    print("=" * 60)
    
    config1 = get_config()
    config2 = get_config()
    
    # 验证是同一个实例
    assert config1 is config2, "全局配置应该是单例"
    print(f"✓ 全局配置单例验证通过")
    
    # 修改一个，另一个也应该改变
    config1.set("regime.attack_threshold", 80)
    threshold_from_config2 = config2.get("regime.attack_threshold")
    print(f"✓ 单例同步验证: {threshold_from_config2}")
    
    return True


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print(">>> 开始测试配置模块")
    print("=" * 60)
    
    tests = [
        test_basic_config,
        test_style_weights,
        test_indicator_config,
        test_set_and_save,
        test_soft_confirm_weights,
        test_global_config
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"\n❌ 测试失败: {test.__name__}")
            print(f"   错误: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(">>> 测试结果汇总")
    print("=" * 60)
    print(f"通过: {passed}/{len(tests)}")
    if failed > 0:
        print(f"失败: {failed}/{len(tests)}")
    else:
        print(f"\n>>> 所有测试通过！阶段1配置模块验证成功。")
    print("=" * 60)


if __name__ == "__main__":
    main()

